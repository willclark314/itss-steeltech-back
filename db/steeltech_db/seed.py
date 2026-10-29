"""开发环境 SQLite 种子数据，与前端 mock 结构对齐。"""

from __future__ import annotations

import json
import sqlite3
from calendar import monthrange
from datetime import date, datetime
from pathlib import Path

from flask import Flask
from sqlalchemy import text

from steeltech_db.config import BaseConfig
from steeltech_db.defaults import (
    BACKUP_CONFIG_KEY,
    DEFAULT_BACKUP_CONFIG,
    DEFAULT_LOCAL_WORK_PATH,
    SETTINGS_KEY,
)
from steeltech_db.extensions import db
from steeltech_db.project_split import (
    LEGACY_PROJECT_SPLIT_SEP,
    PROCESSING_CONTACT_LABEL,
    PROCESSING_CONTACT_PREFIX,
    PROJECT_SPLIT_SEP,
    is_processing_contact_id,
    is_split_project_no,
    parse_base_project_no,
)
from steeltech_db.models import (
    AccountPassword,
    DrawingIssuePlan,
    MonthlyRest,
    Permission,
    Personnel,
    PersonnelLeavePolicy,
    Project,
    ProjectDesignWorkflow,
    ProjectNature,
    ProjectPersonnel,
    Role,
    RolePermission,
    RolePersonnel,
    SystemSetting,
)
from steeltech_db.permission_catalog import (
    ACTION_LABELS,
    LEGACY_WRITE_ACTIONS,
    build_permission_catalog,
)

DEV_USER_PROFILES = {
    "admin": {
        "id": "DEV001",
        "name": "管理员",
        "employeeNo": "42609901",
        "team": "开发组",
        "workshop": "开发人员",
        "position": "开发",
    },
    "user": {
        "id": "DEV002",
        "name": "测试用户",
        "employeeNo": "42609903",
        "team": "开发组",
        "workshop": "开发人员",
        "position": "细化工程师",
    },
}


def _get_package_schema_path() -> Path:
    return Path(__file__).resolve().parent.parent / "datas" / "schema.sql"


def bootstrap_sqlite_file(
    target: Path,
    *,
    schema_path: Path | None = None,
) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        return target

    if schema_path is None:
        schema_path = _get_package_schema_path()

    if schema_path.exists():
        conn = sqlite3.connect(target)
        try:
            conn.executescript(schema_path.read_text(encoding="utf-8"))
            conn.commit()
        finally:
            conn.close()
    return target


def _ensure_columns(table: str, *column_defs: str) -> None:
    """跨数据库为已有表补充缺失字段（使用 SQLAlchemy inspector，兼容 SQLite / MySQL）。"""
    inspector = db.inspect(db.engine)
    existing = {col["name"] for col in inspector.get_columns(table)}
    for column_def in column_defs:
        col_name = column_def.strip().split()[0]
        if col_name not in existing:
            db.session.execute(text(f"ALTER TABLE {table} ADD COLUMN {column_def}"))
    db.session.commit()


def _ensure_index(
    table: str,
    index_name: str,
    *columns: str,
    unique: bool = False,
) -> None:
    """跨数据库创建缺失索引。

    SQLite 支持 CREATE INDEX IF NOT EXISTS；MySQL 不支持该语法，需先检查再创建。
    """
    cols = ", ".join(columns)
    kind = "UNIQUE INDEX" if unique else "INDEX"
    bind = db.session.get_bind()
    if bind.dialect.name == "sqlite":
        db.session.execute(
            text(f"CREATE {kind} IF NOT EXISTS {index_name} ON {table} ({cols})")
        )
        return

    inspector = db.inspect(db.engine)
    existing = {idx["name"] for idx in inspector.get_indexes(table)}
    if index_name in existing:
        return
    db.session.execute(text(f"CREATE {kind} {index_name} ON {table} ({cols})"))


def _is_mysql() -> bool:
    return db.session.get_bind().dialect.name == "mysql"


def _str(length: int = 64) -> str:
    """可用于主键 / 唯一约束 / 索引的字符串类型：SQLite TEXT，MySQL VARCHAR(n)。"""
    return f"VARCHAR({length})" if _is_mysql() else "TEXT"


def _long_text() -> str:
    """非键长文本，两端均用 TEXT。"""
    return "TEXT"


def _float_type() -> str:
    return "DOUBLE" if _is_mysql() else "REAL"


def _next_permission_id() -> str:
    rows = db.session.query(Permission.id).filter(Permission.id.like("PERM%")).all()
    if not rows:
        return "PERM001"
    max_num = max(int(row[0].replace("PERM", "")) for row in rows)
    return f"PERM{max_num + 1:03d}"


def _upsert_permission_catalog(now: str) -> list[str]:
    catalog = build_permission_catalog()
    existing_by_code = {row.code: row for row in Permission.query.all()}
    created_ids: list[str] = []

    for item in catalog:
        existing = existing_by_code.get(item["code"])
        if existing is None:
            perm_id = _next_permission_id()
            db.session.add(
                Permission(
                    id=perm_id,
                    code=item["code"],
                    name=item["name"],
                    module=item["module"],
                    path=item["path"],
                    page_key=item["page_key"],
                    page_name=item["page_name"],
                    action=item["action"],
                    created_at=now,
                )
            )
            created_ids.append(perm_id)
            continue

        existing.name = item["name"]
        existing.module = item["module"]
        existing.path = item["path"]
        existing.page_key = item["page_key"]
        existing.page_name = item["page_name"]
        existing.action = item["action"]

    return created_ids


def _migrate_legacy_write_permissions(now: str) -> None:
    legacy_rows = Permission.query.filter(Permission.action.in_(list(LEGACY_WRITE_ACTIONS))).all()
    if not legacy_rows:
        return

    for legacy in legacy_rows:
        RolePermission.query.filter_by(permission_id=legacy.id).delete()
        db.session.delete(legacy)


def _remove_edit_permissions() -> None:
    edit_rows = Permission.query.filter_by(action="edit").all()
    if not edit_rows:
        return

    edit_ids = [row.id for row in edit_rows]
    RolePermission.query.filter(RolePermission.permission_id.in_(edit_ids)).delete(
        synchronize_session=False
    )
    Permission.query.filter(Permission.id.in_(edit_ids)).delete(synchronize_session=False)


def _grant_new_permissions_to_admin(permission_ids: list[str], now: str) -> None:
    """仅为管理员补全新入库的页面权限，不覆盖已有角色授权。"""
    if not permission_ids:
        return

    admin_role = Role.query.filter_by(code="admin").first()
    if admin_role is None:
        return

    existing_permission_ids = {
        row.permission_id
        for row in RolePermission.query.filter_by(role_id=admin_role.id).all()
    }
    for permission_id in permission_ids:
        if permission_id in existing_permission_ids:
            continue
        db.session.add(
            RolePermission(
                role_id=admin_role.id,
                permission_id=permission_id,
                created_at=now,
            )
        )


def migrate_permission_view_all_constraint() -> None:
    """重建 permissions 表 CHECK，使 action 支持 view-all。"""
    bind = db.session.get_bind()
    if bind.dialect.name != "sqlite":
        return

    ddl = db.session.execute(
        text("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'permissions'")
    ).scalar()
    if not ddl or "view-all" in ddl:
        return

    rows = [
        dict(row)
        for row in db.session.execute(text("SELECT * FROM permissions")).mappings().all()
    ]
    role_links = [
        dict(row)
        for row in db.session.execute(text("SELECT * FROM role_permissions")).mappings().all()
    ]
    valid_perm_ids = {row["id"] for row in rows}

    insert_perm = text(
        """
        INSERT INTO permissions_new (
          id, code, name, module, path, page_key, page_name, action, created_at
        ) VALUES (
          :id, :code, :name, :module, :path, :page_key, :page_name, :action, :created_at
        )
        """
    )
    insert_link = text(
        """
        INSERT INTO role_permissions_new (role_id, permission_id, created_at)
        VALUES (:role_id, :permission_id, :created_at)
        """
    )

    db.session.execute(text("PRAGMA foreign_keys = OFF"))
    db.session.execute(text("DROP TABLE IF EXISTS permissions_new"))
    db.session.execute(text("DROP TABLE IF EXISTS role_permissions_new"))
    db.session.execute(
        text(
            """
            CREATE TABLE permissions_new (
              id          TEXT PRIMARY KEY,
              code        TEXT NOT NULL UNIQUE,
              name        TEXT NOT NULL,
              module      TEXT NOT NULL,
              path        TEXT NOT NULL,
              page_key    TEXT NOT NULL,
              page_name   TEXT NOT NULL,
              action      TEXT NOT NULL,
              created_at  TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
              CHECK (action IN ('view', 'edit', 'view-all'))
            )
            """
        )
    )
    for row in rows:
        db.session.execute(insert_perm, row)

    db.session.execute(text("DROP TABLE permissions"))
    db.session.execute(text("ALTER TABLE permissions_new RENAME TO permissions"))
    _ensure_index("permissions", "idx_permissions_module", "module")

    db.session.execute(
        text(
            """
            CREATE TABLE role_permissions_new (
              role_id       TEXT NOT NULL,
              permission_id TEXT NOT NULL,
              created_at    TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
              PRIMARY KEY (role_id, permission_id),
              FOREIGN KEY (role_id) REFERENCES roles (id) ON DELETE CASCADE,
              FOREIGN KEY (permission_id) REFERENCES permissions (id) ON DELETE CASCADE
            )
            """
        )
    )
    seen_links: set[tuple[str, str]] = set()
    for link in role_links:
        perm_id = link["permission_id"]
        if perm_id not in valid_perm_ids:
            continue
        key = (link["role_id"], perm_id)
        if key in seen_links:
            continue
        seen_links.add(key)
        db.session.execute(insert_link, link)

    db.session.execute(text("DROP TABLE role_permissions"))
    db.session.execute(text("ALTER TABLE role_permissions_new RENAME TO role_permissions"))
    _ensure_index("role_permissions", "idx_role_permissions_role_id", "role_id")
    db.session.execute(text("PRAGMA foreign_keys = ON"))
    db.session.commit()


def migrate_permission_action_constraint() -> None:
    """重建 permissions 表，使 action 支持 view/edit，并合并旧版 create/update/delete。"""
    bind = db.session.get_bind()
    if bind.dialect.name != "sqlite":
        return

    ddl = db.session.execute(
        text("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'permissions'")
    ).scalar()
    if not ddl or "'edit'" in ddl:
        return

    rows = [
        dict(row)
        for row in db.session.execute(text("SELECT * FROM permissions")).mappings().all()
    ]
    role_links = [
        dict(row)
        for row in db.session.execute(text("SELECT * FROM role_permissions")).mappings().all()
    ]

    view_rows = [row for row in rows if row["action"] == "view"]
    legacy_rows = [row for row in rows if row["action"] in LEGACY_WRITE_ACTIONS]

    perm_nums = [
        int(row["id"].replace("PERM", ""))
        for row in rows
        if str(row["id"]).startswith("PERM") and str(row["id"][4:]).isdigit()
    ]
    next_perm_num = max(perm_nums, default=0) + 1

    legacy_by_page: dict[str, list[dict]] = {}
    for row in legacy_rows:
        legacy_by_page.setdefault(row["page_key"], []).append(row)

    edit_rows: list[dict] = []
    legacy_to_edit_id: dict[str, str] = {}
    for page_key, page_legacy_rows in legacy_by_page.items():
        sample = page_legacy_rows[0]
        edit_id = f"PERM{next_perm_num:03d}"
        next_perm_num += 1
        edit_rows.append(
            {
                "id": edit_id,
                "code": f"{page_key}:edit",
                "name": ACTION_LABELS["edit"],
                "module": sample["module"],
                "path": sample["path"],
                "page_key": page_key,
                "page_name": sample["page_name"],
                "action": "edit",
                "created_at": min(row["created_at"] for row in page_legacy_rows),
            }
        )
        for legacy in page_legacy_rows:
            legacy_to_edit_id[legacy["id"]] = edit_id

    new_permissions = view_rows + edit_rows
    valid_perm_ids = {row["id"] for row in new_permissions}

    seen_links: set[tuple[str, str]] = set()
    new_role_links: list[dict] = []
    for link in role_links:
        perm_id = link["permission_id"]
        if perm_id in legacy_to_edit_id:
            perm_id = legacy_to_edit_id[perm_id]
        elif perm_id not in valid_perm_ids:
            continue
        key = (link["role_id"], perm_id)
        if key in seen_links:
            continue
        seen_links.add(key)
        new_role_links.append({**link, "permission_id": perm_id})

    insert_perm = text(
        """
        INSERT INTO permissions_new (
          id, code, name, module, path, page_key, page_name, action, created_at
        ) VALUES (
          :id, :code, :name, :module, :path, :page_key, :page_name, :action, :created_at
        )
        """
    )
    insert_link = text(
        """
        INSERT INTO role_permissions_new (role_id, permission_id, created_at)
        VALUES (:role_id, :permission_id, :created_at)
        """
    )

    db.session.execute(text("PRAGMA foreign_keys = OFF"))
    db.session.execute(text("DROP TABLE IF EXISTS permissions_new"))
    db.session.execute(text("DROP TABLE IF EXISTS role_permissions_new"))
    db.session.execute(
        text(
            """
            CREATE TABLE permissions_new (
              id          TEXT PRIMARY KEY,
              code        TEXT NOT NULL UNIQUE,
              name        TEXT NOT NULL,
              module      TEXT NOT NULL,
              path        TEXT NOT NULL,
              page_key    TEXT NOT NULL,
              page_name   TEXT NOT NULL,
              action      TEXT NOT NULL,
              created_at  TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
              CHECK (action IN ('view', 'edit', 'view-all'))
            )
            """
        )
    )
    for row in new_permissions:
        db.session.execute(insert_perm, row)

    db.session.execute(text("DROP TABLE permissions"))
    db.session.execute(text("ALTER TABLE permissions_new RENAME TO permissions"))
    _ensure_index("permissions", "idx_permissions_module", "module")

    db.session.execute(
        text(
            """
            CREATE TABLE role_permissions_new (
              role_id       TEXT NOT NULL,
              permission_id TEXT NOT NULL,
              created_at    TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
              PRIMARY KEY (role_id, permission_id),
              FOREIGN KEY (role_id) REFERENCES roles (id) ON DELETE CASCADE,
              FOREIGN KEY (permission_id) REFERENCES permissions (id) ON DELETE CASCADE
            )
            """
        )
    )
    for link in new_role_links:
        db.session.execute(insert_link, link)

    db.session.execute(text("DROP TABLE role_permissions"))
    db.session.execute(text("ALTER TABLE role_permissions_new RENAME TO role_permissions"))
    _ensure_index("role_permissions", "idx_role_permissions_role_id", "role_id")
    db.session.execute(text("PRAGMA foreign_keys = ON"))
    db.session.commit()


def sync_permission_catalog() -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    new_permission_ids = _upsert_permission_catalog(now)
    db.session.flush()
    _migrate_legacy_write_permissions(now)
    _remove_edit_permissions()
    _grant_new_permissions_to_admin(new_permission_ids, now)

    db.session.commit()


# 细化工程师（detailer）角色默认权限 codes
DETAILER_PERMISSION_CODES = [
    "home:view",
    "my:view",
    "about:view",
    "guide:view",
    "contact-browse:view",
    "project-browse:view",
    "design-drawing-issue-plan:view",
    "drawing-issue-plan:view",
    "settlement-record:view",
    "project-model:view",
    "leave:view",
    "monthly-rest:view",
]


def _ensure_detailer_role(now: str) -> None:
    """确保细化工程师（detailer）角色存在；默认权限仅在首次创建时写入。"""
    detailer_role = Role.query.filter_by(code="detailer").first()
    is_new = detailer_role is None
    if is_new:
        detailer_role = Role(
            id="ROLE006",
            name="细化工程师",
            code="detailer",
            description="业务页面仅查看，不可新增或修改",
            status="active",
            created_at=now,
            updated_at=now,
        )
        db.session.add(detailer_role)
        db.session.flush()
        _ensure_role_permissions(detailer_role, DETAILER_PERMISSION_CODES, now)


def _grant_monthly_rest_to_leave_roles(now: str) -> None:
    """为已有年休查看权限的角色补全月休查看权限（与旧版全员可见行为一致）。"""
    leave_perm = Permission.query.filter_by(code="leave:view").first()
    monthly_rest_perm = Permission.query.filter_by(code="monthly-rest:view").first()
    if leave_perm is None or monthly_rest_perm is None:
        return

    role_ids_with_leave = {
        row.role_id
        for row in RolePermission.query.filter_by(permission_id=leave_perm.id).all()
    }
    if not role_ids_with_leave:
        return

    existing_role_ids = {
        row.role_id
        for row in RolePermission.query.filter_by(permission_id=monthly_rest_perm.id).all()
    }
    for role_id in role_ids_with_leave:
        if role_id in existing_role_ids:
            continue
        db.session.add(
            RolePermission(
                role_id=role_id,
                permission_id=monthly_rest_perm.id,
                created_at=now,
            )
        )


def _grant_production_pages_to_change_order_browse_roles(now: str) -> None:
    """为已有生产计划「变更单」权限的角色补全联系单登记、项目浏览权限。"""
    source_perm = Permission.query.filter_by(code="change-order-browse:view").first()
    if source_perm is None:
        return

    target_perms = [
        Permission.query.filter_by(code=code).first()
        for code in ("production-contact:view", "production-project-browse:view")
    ]
    target_perms = [perm for perm in target_perms if perm is not None]
    if not target_perms:
        return

    role_ids = {
        row.role_id
        for row in RolePermission.query.filter_by(permission_id=source_perm.id).all()
    }
    if not role_ids:
        return

    for target_perm in target_perms:
        existing_role_ids = {
            row.role_id
            for row in RolePermission.query.filter_by(permission_id=target_perm.id).all()
        }
        for role_id in role_ids:
            if role_id in existing_role_ids:
                continue
            db.session.add(
                RolePermission(
                    role_id=role_id,
                    permission_id=target_perm.id,
                    created_at=now,
                )
            )


def _ensure_role_permissions(role: Role, permission_codes: list[str], now: str) -> None:
    """为角色写入默认权限（仅追加缺失项，供首次创建角色时使用）。"""
    perm_ids = [
        row.id
        for row in Permission.query.filter(Permission.code.in_(permission_codes)).all()
    ]
    existing_perm_ids = {
        row.permission_id
        for row in RolePermission.query.filter_by(role_id=role.id).all()
    }
    for perm_id in perm_ids:
        if perm_id not in existing_perm_ids:
            db.session.add(
                RolePermission(
                    role_id=role.id,
                    permission_id=perm_id,
                    created_at=now,
                )
            )


def _find_personnel_by_names(names: list[str]) -> Personnel | None:
    for name in names:
        person = Personnel.query.filter_by(name=name).first()
        if person is not None:
            return person
    return None


def _ensure_role_personnel(role: Role, personnel_names: list[str], now: str) -> Personnel | None:
    person = _find_personnel_by_names(personnel_names)
    if person is None:
        return None
    existing = RolePersonnel.query.filter_by(
        role_id=role.id,
        personnel_id=person.id,
    ).first()
    if existing is None:
        db.session.add(
            RolePersonnel(
                role_id=role.id,
                personnel_id=person.id,
                created_at=now,
            )
        )
    return person


def _remove_personnel_from_role_by_code(person: Personnel, role_code: str) -> None:
    role = Role.query.filter_by(code=role_code).first()
    if role is None:
        return
    link = RolePersonnel.query.filter_by(
        role_id=role.id,
        personnel_id=person.id,
    ).first()
    if link is not None:
        db.session.delete(link)


def _ensure_detail_team_special_roles(now: str) -> None:
    """确保调图员、排板员角色存在，并关联对应人员。"""
    drawing_role = Role.query.filter_by(code="drawing-operator").first()
    if drawing_role is None:
        drawing_role = Role(
            id="ROLE007",
            name="调图员",
            code="drawing-operator",
            description="负责项目调图阶段",
            status="active",
            created_at=now,
            updated_at=now,
        )
        db.session.add(drawing_role)
        db.session.flush()
        _ensure_role_permissions(drawing_role, DETAILER_PERMISSION_CODES, now)

    plate_layout_role = Role.query.filter_by(code="plate-layout-operator").first()
    if plate_layout_role is None:
        plate_layout_role = Role(
            id="ROLE008",
            name="排板员",
            code="plate-layout-operator",
            description="负责项目钢板排板阶段",
            status="active",
            created_at=now,
            updated_at=now,
        )
        db.session.add(plate_layout_role)
        db.session.flush()
        _ensure_role_permissions(plate_layout_role, DETAILER_PERMISSION_CODES, now)

    drawing_person = _ensure_role_personnel(drawing_role, ["陈姜宏"], now)
    if drawing_person is not None:
        _remove_personnel_from_role_by_code(drawing_person, "detailer")

    plate_person = _ensure_role_personnel(
        plate_layout_role,
        ["林良峰", "林良锋"],
        now,
    )
    if plate_person is not None:
        _remove_personnel_from_role_by_code(plate_person, "detailer")


def _ensure_clerk_roles(now: str) -> None:
    """确保设计文员、细化文员角色存在。"""
    design_clerk = Role.query.filter_by(code="design-clerk").first()
    if design_clerk is None:
        design_clerk = Role(
            id="ROLE009",
            name="设计文员",
            code="design-clerk",
            description="设计组文员，可查看业务页面",
            status="active",
            created_at=now,
            updated_at=now,
        )
        db.session.add(design_clerk)
        db.session.flush()
        _ensure_role_permissions(design_clerk, DETAILER_PERMISSION_CODES, now)

    detail_clerk = Role.query.filter_by(code="detail-clerk").first()
    if detail_clerk is None:
        detail_clerk = Role(
            id="ROLE010",
            name="细化文员",
            code="detail-clerk",
            description="细化组文员，可查看业务页面",
            status="active",
            created_at=now,
            updated_at=now,
        )
        db.session.add(detail_clerk)
        db.session.flush()
        _ensure_role_permissions(detail_clerk, DETAILER_PERMISSION_CODES, now)

    db.session.commit()


def resolve_dev_personnel_id(profile: dict) -> str | None:
    """解析 DEV profile 对应的真实 personnel.id（优先 DEV id，其次工号）。"""
    person = Personnel.query.filter_by(id=profile["id"]).first()
    if person is None:
        person = Personnel.query.filter_by(employee_no=profile["employeeNo"]).first()
    return person.id if person is not None else None


def ensure_dev_users(app: Flask) -> None:
    """确保 DEV_USER_PROFILES 中定义的测试用户存在于 Personnel 和 AccountPassword 表中。"""
    default_password = app.config["DEFAULT_LOGIN_PASSWORD"]
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    resolved_ids: dict[str, str] = {}

    for account, profile in DEV_USER_PROFILES.items():
        dev_id = profile["id"]
        dev_employee_no = profile["employeeNo"]

        # 先按 DEV id 查
        existing = Personnel.query.filter_by(id=dev_id).first()
        if existing is None:
            # 再按工号查，防止不同 id 相同工号重复
            existing = Personnel.query.filter_by(employee_no=dev_employee_no).first()

        if existing is None:
            # 新建 Personnel 记录
            db.session.add(
                Personnel(
                    id=dev_id,
                    name=profile["name"],
                    employee_no=dev_employee_no,
                    team=profile["team"],
                    position=profile.get("position", ""),
                    nationality="中国",
                    workshop=profile.get("workshop", "开发人员"),
                    status="active",
                    created_at=now,
                    updated_at=now,
                )
            )
            resolved_ids[account] = dev_id
        else:
            # 确保工号、班组、科室与 DEV profile 一致
            changed = False
            if existing.employee_no != dev_employee_no:
                existing.employee_no = dev_employee_no
                changed = True
            if existing.team != profile["team"]:
                existing.team = profile["team"]
                changed = True
            expected_workshop = profile.get("workshop", "开发人员")
            if (existing.workshop or "").strip() != expected_workshop:
                existing.workshop = expected_workshop
                changed = True
            if changed:
                existing.updated_at = now
            resolved_ids[account] = existing.id

        # 确保账号密码存在（dev 账号名，如 "admin"、"user"）
        if AccountPassword.query.filter_by(account=account).first() is None:
            db.session.add(
                AccountPassword(
                    account=account,
                    password=default_password,
                    updated_at=now,
                )
            )

        # 确保工号密码存在
        if AccountPassword.query.filter_by(account=dev_employee_no).first() is None:
            db.session.add(
                AccountPassword(
                    account=dev_employee_no,
                    password=default_password,
                    updated_at=now,
                )
            )

    # 确保 "user" 账号有 detailer 角色
    user_profile = DEV_USER_PROFILES.get("user")
    _ensure_dev_role(user_profile, "detailer", now, resolved_ids.get("user"))

    # 确保 "admin" 账号有 admin 角色
    admin_profile = DEV_USER_PROFILES.get("admin")
    _ensure_dev_role(admin_profile, "admin", now, resolved_ids.get("admin"))

    db.session.commit()


def migrate_dev_team_workshop() -> None:
    """将开发组人员科室统一为「开发人员」。"""
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rows = Personnel.query.filter_by(team="开发组").all()
    changed = False
    for row in rows:
        if (row.workshop or "").strip() != "开发人员":
            row.workshop = "开发人员"
            row.updated_at = now
            changed = True
    if changed:
        db.session.commit()


def _ensure_dev_role(
    profile: dict | None,
    role_code: str,
    now: str,
    personnel_id: str | None = None,
) -> None:
    """为 DEV profile 分配指定角色（绑定到真实存在的 personnel.id）。"""
    if profile is None:
        return
    role = Role.query.filter_by(code=role_code).first()
    if role is None:
        return
    target_id = personnel_id or resolve_dev_personnel_id(profile) or profile["id"]
    existing = RolePersonnel.query.filter_by(
        role_id=role.id, personnel_id=target_id
    ).first()
    if existing is None:
        db.session.add(
            RolePersonnel(
                role_id=role.id,
                personnel_id=target_id,
                created_at=now,
            )
        )


def ensure_system_settings() -> None:
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # local_work_path
    if SystemSetting.query.filter_by(key=SETTINGS_KEY).first() is None:
        db.session.add(
            SystemSetting(
                key=SETTINGS_KEY,
                value=json.dumps(DEFAULT_LOCAL_WORK_PATH.to_dict(), ensure_ascii=False),
                updated_at=now,
            )
        )

    # backup_config
    if SystemSetting.query.filter_by(key=BACKUP_CONFIG_KEY).first() is None:
        db.session.add(
            SystemSetting(
                key=BACKUP_CONFIG_KEY,
                value=json.dumps(DEFAULT_BACKUP_CONFIG.to_dict(), ensure_ascii=False),
                updated_at=now,
            )
        )

    db.session.commit()


def migrate_contact_form_relations_ddl() -> None:
    """跨数据库补建 contact_form 相关字段和索引（使用 SQLAlchemy inspector）。"""
    s, lt = _str, _long_text
    _ensure_columns(
        "contact_forms",
        f"parent_id {s()}",
        f"root_id {s()}",
        f"relation_type {s(32)} NOT NULL DEFAULT 'primary'",
        "sort_order INTEGER NOT NULL DEFAULT 0",
        f"cancel_scope {s(16)}",
        f"deleted_at {s(32)}",
        f"derived_family_max_date {s(32)}",
    )
    _ensure_columns(
        "contact_form_projects",
        f"source_type {s(16)} NOT NULL DEFAULT 'own'",
        f"source_contact_form_id {s()}",
    )
    _ensure_columns(
        "contact_form_pdfs",
        f"attachment_type {s(16)} NOT NULL DEFAULT 'supplement'",
        f"remark {lt()}",
        f"file_md5 {s(32)}",
        "is_current INTEGER NOT NULL DEFAULT 1",
        f"original_file_name {s(256)}",
        f"deleted_at {s(32)}",
    )

    db.session.execute(
        text(
            f"""
            CREATE TABLE IF NOT EXISTS contact_form_project_cancellations (
              id                {s()} PRIMARY KEY,
              cancel_contact_id {s()} NOT NULL,
              target_contact_id {s()} NOT NULL,
              project_no        {s()} NOT NULL,
              cancelled_at      {s(32)} NOT NULL
            )
            """
        )
    )
    _ensure_index("contact_form_pdfs", "idx_contact_form_pdfs_md5", "file_md5")
    _ensure_index("contact_forms", "idx_contact_forms_deleted_at", "deleted_at")
    _ensure_index("contact_form_pdfs", "idx_contact_form_pdfs_deleted_at", "deleted_at")
    db.session.commit()


def migrate_contact_form_relations() -> None:
    """SQLite 专属：历史数据修复迁移（填充 root_id、relation_type、is_current 等）。"""
    # 先执行跨数据库的 DDL 补字段
    migrate_contact_form_relations_ddl()

    bind = db.session.get_bind()
    if bind.dialect.name != "sqlite":
        return

    conn = db.engine.raw_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE contact_forms SET root_id = id WHERE IFNULL(root_id, '') = ''")
        cursor.execute(
            "UPDATE contact_forms SET relation_type = 'primary' WHERE IFNULL(relation_type, '') = ''"
        )
        # 同一家族内按主单 -> 补充/变更/跟进/取消重算 sort_order，保证列表主单在前
        cursor.execute(
            """
            UPDATE contact_forms
            SET sort_order = (
              SELECT ordered.rn
              FROM (
                SELECT id,
                  ROW_NUMBER() OVER (
                    PARTITION BY COALESCE(root_id, id)
                    ORDER BY
                      CASE WHEN id = COALESCE(root_id, id) THEN 0 ELSE 1 END,
                      created_at,
                      id
                  ) - 1 AS rn
                FROM contact_forms
                WHERE deleted_at IS NULL
              ) AS ordered
              WHERE ordered.id = contact_forms.id
            )
            WHERE deleted_at IS NULL
            """
        )

        pdf_columns = {row[1] for row in cursor.execute("PRAGMA table_info(contact_form_pdfs)").fetchall()}
        if "is_current" in pdf_columns:
            cursor.execute(
                "UPDATE contact_form_pdfs SET is_current = 0 WHERE attachment_type = 'primary'"
            )
            cursor.execute(
                """
                UPDATE contact_form_pdfs
                SET is_current = 1
                WHERE attachment_type = 'primary'
                  AND id IN (
                    SELECT p.id
                    FROM contact_form_pdfs AS p
                    INNER JOIN (
                      SELECT contact_form_id, MAX(created_at) AS max_created
                      FROM contact_form_pdfs
                      WHERE attachment_type = 'primary'
                      GROUP BY contact_form_id
                    ) AS latest
                      ON p.contact_form_id = latest.contact_form_id
                     AND p.created_at = latest.max_created
                  )
                """
            )
        conn.commit()
    finally:
        conn.close()


def _get_sundays_of_month(year: int, month: int) -> list[str]:
    """获取指定月份所有星期日的日期字符串列表"""
    sundays: list[str] = []
    _, days_in_month = monthrange(year, month)
    for day in range(1, days_in_month + 1):
        d = date(year, month, day)
        if d.weekday() == 6:  # 周日
            sundays.append(d.strftime("%Y-%m-%d"))
    return sundays


def seed_default_monthly_rest() -> list[dict]:
    """
    为所有在职人员补全当月默认月休。
    中国籍：当月所有周日为休息日；印尼籍：默认不选，由员工自行选择 1-4 天。
    已有当月记录的人员不会被覆盖。
    每次应用启动时调用，确保新月份自动有默认数据。
    """
    now = datetime.now()
    year = now.year
    month = now.month
    sundays = _get_sundays_of_month(year, month)
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")

    active_personnel = Personnel.query.filter_by(status="active").all()
    created: list[dict] = []

    for person in active_personnel:
        record_id = f"{person.id}_{year}_{str(month).zfill(2)}"
        existing = MonthlyRest.query.get(record_id)
        if existing:
            # 已有当月记录，不动
            continue
        default_rest_days = (
            []
            if (person.nationality or "").strip() == "印度尼西亚"
            else sundays
        )
        record = MonthlyRest(
            id=record_id,
            personnel_id=person.id,
            year=year,
            month=month,
            rest_days=json.dumps(default_rest_days, ensure_ascii=False),
            created_at=now_str,
            updated_at=now_str,
        )
        db.session.add(record)
        created.append(record.to_dict())

    if created:
        db.session.commit()
    return created


def drop_legacy_users_table() -> None:
    """移除已废弃的 users 表（认证统一使用 account_passwords + personnel）。"""
    if "users" not in db.inspect(db.engine).get_table_names():
        return
    db.session.execute(text("DROP TABLE users"))
    db.session.commit()


def seed_default_leave_policies() -> list[dict]:
    """
    为所有在职且尚无休假策略的人员自动创建默认策略。
    - workDays = 150, leaveDays = 19
    - cycleStartDate 按人员索引均匀错开，使休假时段分散全年
    """
    from datetime import date as date_cls

    active_personnel = Personnel.query.filter_by(status="active").order_by(Personnel.team, Personnel.name).all()
    existing_ids = {r.personnel_id for r in PersonnelLeavePolicy.query.all()}
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    total = len(active_personnel) or 1
    cycle_days = 150 + 19  # 169
    stagger_step = max(1, cycle_days // total)
    base_date = date_cls(2020, 1, 1)

    created: list[dict] = []
    for index, person in enumerate(active_personnel):
        if person.id in existing_ids:
            continue
        offset = index * stagger_step
        cycle_start = date_cls.fromordinal(base_date.toordinal() + offset)
        policy = PersonnelLeavePolicy(
            id=f"POL_{person.id}",
            personnel_id=person.id,
            work_days=150,
            leave_days=19,
            cycle_start_date=cycle_start.isoformat(),
            effective_from=base_date.isoformat(),
            created_at=now_str,
            updated_at=now_str,
        )
        db.session.add(policy)
        created.append(policy.to_dict())

    if created:
        db.session.commit()
    return created


def migrate_project_completion_flags() -> None:
    inspector = db.inspect(db.engine)
    columns = {column["name"] for column in inspector.get_columns("projects")}

    if "design_completed" not in columns:
        db.session.execute(
            text(
                "ALTER TABLE projects ADD COLUMN design_completed INTEGER NOT NULL DEFAULT 0 "
                "CHECK (design_completed IN (0, 1))"
            )
        )

    if "detail_completed" not in columns:
        db.session.execute(
            text(
                "ALTER TABLE projects ADD COLUMN detail_completed INTEGER NOT NULL DEFAULT 0 "
                "CHECK (detail_completed IN (0, 1))"
            )
        )

    if "tile_layout_completed" not in columns:
        db.session.execute(
            text(
                "ALTER TABLE projects ADD COLUMN tile_layout_completed INTEGER NOT NULL DEFAULT 0 "
                "CHECK (tile_layout_completed IN (0, 1))"
            )
        )

    if "floor_deck_layout_completed" not in columns:
        db.session.execute(
            text(
                "ALTER TABLE projects ADD COLUMN floor_deck_layout_completed INTEGER NOT NULL DEFAULT 0 "
                "CHECK (floor_deck_layout_completed IN (0, 1))"
            )
        )

    db.session.commit()


def migrate_project_structure_and_weight() -> None:
    inspector = db.inspect(db.engine)
    columns = {column["name"] for column in inspector.get_columns("projects")}

    if "structure_type" not in columns:
        db.session.execute(text("ALTER TABLE projects ADD COLUMN structure_type TEXT"))

    if "estimated_weight_tons" not in columns:
        db.session.execute(text("ALTER TABLE projects ADD COLUMN estimated_weight_tons REAL"))

    db.session.commit()


def migrate_project_drawing_issue_fields() -> None:
    inspector = db.inspect(db.engine)
    columns = {column["name"] for column in inspector.get_columns("projects")}

    if "drawing_issue_enabled" not in columns:
        db.session.execute(
            text(
                "ALTER TABLE projects ADD COLUMN drawing_issue_enabled INTEGER NOT NULL DEFAULT 0 "
                "CHECK (drawing_issue_enabled IN (0, 1))"
            )
        )

    if "drawing_issue_year_month" not in columns:
        db.session.execute(text("ALTER TABLE projects ADD COLUMN drawing_issue_year_month TEXT"))

    db.session.commit()


def migrate_project_work_paths() -> None:
    inspector = db.inspect(db.engine)
    columns = {column["name"] for column in inspector.get_columns("projects")}

    if "design_work_path" not in columns:
        db.session.execute(text("ALTER TABLE projects ADD COLUMN design_work_path TEXT"))

    if "detail_work_path" not in columns:
        db.session.execute(text("ALTER TABLE projects ADD COLUMN detail_work_path TEXT"))

    if "derived_received_date" not in columns:
        db.session.execute(text("ALTER TABLE projects ADD COLUMN derived_received_date TEXT"))

    _ensure_index("projects", "idx_projects_derived_received_date", "derived_received_date")

    db.session.execute(
        text(
            """
            UPDATE projects
            SET design_work_path = CASE
                WHEN IFNULL(TRIM(design_work_path), '') <> '' THEN TRIM(design_work_path)
                WHEN IFNULL(TRIM(local_work_path), '') <> ''
                     AND EXISTS (
                       SELECT 1 FROM project_natures pn
                       WHERE pn.project_no = projects.project_no AND pn.nature = 'design'
                     )
                     AND (
                       NOT EXISTS (
                         SELECT 1 FROM project_natures pn
                         WHERE pn.project_no = projects.project_no AND pn.nature = 'detail'
                       )
                       OR local_work_path LIKE '%设计%'
                     )
                THEN TRIM(local_work_path)
                ELSE IFNULL(design_work_path, '')
            END,
            detail_work_path = CASE
                WHEN IFNULL(TRIM(detail_work_path), '') <> '' THEN TRIM(detail_work_path)
                WHEN IFNULL(TRIM(local_work_path), '') <> ''
                     AND EXISTS (
                       SELECT 1 FROM project_natures pn
                       WHERE pn.project_no = projects.project_no AND pn.nature = 'detail'
                     )
                     AND (
                       NOT EXISTS (
                         SELECT 1 FROM project_natures pn
                         WHERE pn.project_no = projects.project_no AND pn.nature = 'design'
                       )
                       OR local_work_path LIKE '%深化%'
                       OR local_work_path LIKE '%加工单%'
                     )
                THEN TRIM(local_work_path)
                ELSE IFNULL(detail_work_path, '')
            END
            """
        )
    )

    db.session.commit()


def migrate_project_is_jiagongdan() -> None:
    """列表用 is_jiagongdan 落库，避免每次翻页扫描联系单 content。"""
    inspector = db.inspect(db.engine)
    columns = {column["name"] for column in inspector.get_columns("projects")}
    added = "is_jiagongdan" not in columns

    if added:
        if _is_mysql():
            db.session.execute(
                text("ALTER TABLE projects ADD COLUMN is_jiagongdan TINYINT(1) NOT NULL DEFAULT 0")
            )
        else:
            db.session.execute(
                text(
                    "ALTER TABLE projects ADD COLUMN is_jiagongdan INTEGER NOT NULL DEFAULT 0 "
                    "CHECK (is_jiagongdan IN (0, 1))"
                )
            )

        if _is_mysql():
            content_sql = """(
                cf.id LIKE '加工单-%'
                OR cf.id REGEXP '^BRD[0-9]{6}C[0-9]{9}$'
                OR cf.title LIKE '%加工单%'
                OR cf.content LIKE '项目分类：%加工单%'
                OR cf.content LIKE '项目分类:%加工单%'
                OR cf.content LIKE CONCAT('%', CHAR(10), '项目分类：%加工单%')
                OR cf.content LIKE CONCAT('%', CHAR(10), '项目分类:%加工单%')
            )"""
        else:
            content_sql = """(
                cf.id LIKE '加工单-%'
                OR cf.id GLOB 'BRD[0-9][0-9][0-9][0-9][0-9][0-9]C[0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9][0-9]'
                OR cf.title LIKE '%加工单%'
                OR cf.content LIKE '项目分类：%加工单%'
                OR cf.content LIKE '项目分类:%加工单%'
                OR cf.content LIKE '%' || CHAR(10) || '项目分类：%加工单%'
                OR cf.content LIKE '%' || CHAR(10) || '项目分类:%加工单%'
            )"""

        db.session.execute(
            text(
                f"""
                UPDATE projects
                SET is_jiagongdan = CASE WHEN EXISTS (
                    SELECT 1
                    FROM contact_form_projects cfp
                    INNER JOIN contact_forms cf ON cf.id = cfp.contact_form_id
                    WHERE cfp.project_no = projects.project_no
                      AND cf.deleted_at IS NULL
                      AND {content_sql}
                ) THEN 1 ELSE 0 END
                """
            )
        )

    db.session.execute(
        text(
            """
            UPDATE projects
            SET derived_received_date = COALESCE(
                NULLIF(TRIM(received_date), ''),
                NULLIF(TRIM(planned_start_date), ''),
                ''
            )
            WHERE IFNULL(TRIM(derived_received_date), '') = ''
            """
        )
    )
    db.session.commit()


def migrate_project_nature_constraint() -> None:
    """重建 project_natures 表，扩展 nature 可选值。"""
    bind = db.session.get_bind()
    if bind.dialect.name != "sqlite":
        return

    ddl = db.session.execute(
        text("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'project_natures'")
    ).scalar()
    if not ddl or "detail_issue" in ddl:
        return

    rows = [
        dict(row)
        for row in db.session.execute(text("SELECT * FROM project_natures")).mappings().all()
    ]

    db.session.execute(text("PRAGMA foreign_keys = OFF"))
    db.session.execute(text("DROP TABLE IF EXISTS project_natures"))
    db.session.execute(
        text(
            """
            CREATE TABLE project_natures (
              project_no  TEXT NOT NULL,
              nature      TEXT NOT NULL,
              created_at  TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
              PRIMARY KEY (project_no, nature),
              FOREIGN KEY (project_no) REFERENCES projects (project_no) ON DELETE CASCADE,
              CHECK (nature IN ('design', 'detail', 'detail_issue', 'plate_layout', 'tile_layout'))
            )
            """
        )
    )
    _ensure_index("project_natures", "idx_project_natures_project_no", "project_no")

    for row in rows:
        db.session.execute(
            text(
                "INSERT OR IGNORE INTO project_natures (project_no, nature, created_at) "
                "VALUES (:project_no, :nature, :created_at)"
            ),
            row,
        )

    db.session.execute(text("PRAGMA foreign_keys = ON"))
    db.session.commit()


def migrate_project_nature_floor_deck_layout() -> None:
    """重建 project_natures 表，加入 floor_deck_layout（排楼板）可选值。"""
    bind = db.session.get_bind()
    if bind.dialect.name != "sqlite":
        return

    ddl = db.session.execute(
        text("SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'project_natures'")
    ).scalar()
    if not ddl or "floor_deck_layout" in ddl:
        return

    rows = [
        dict(row)
        for row in db.session.execute(text("SELECT * FROM project_natures")).mappings().all()
    ]

    db.session.execute(text("PRAGMA foreign_keys = OFF"))
    db.session.execute(text("DROP TABLE IF EXISTS project_natures"))
    db.session.execute(
        text(
            """
            CREATE TABLE project_natures (
              project_no  TEXT NOT NULL,
              nature      TEXT NOT NULL,
              created_at  TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
              PRIMARY KEY (project_no, nature),
              FOREIGN KEY (project_no) REFERENCES projects (project_no) ON DELETE CASCADE,
              CHECK (nature IN (
                'design', 'detail', 'detail_issue', 'plate_layout', 'floor_deck_layout', 'tile_layout'
              ))
            )
            """
        )
    )
    _ensure_index("project_natures", "idx_project_natures_project_no", "project_no")

    for row in rows:
        db.session.execute(
            text(
                "INSERT OR IGNORE INTO project_natures (project_no, nature, created_at) "
                "VALUES (:project_no, :nature, :created_at)"
            ),
            row,
        )

    db.session.execute(text("PRAGMA foreign_keys = ON"))
    db.session.commit()


def _clone_project_for_split(
    cursor: sqlite3.Cursor,
    source_project_no: str,
    target_project_no: str,
    *,
    received_date: str | None,
    now_text: str,
) -> None:
    row = cursor.execute(
        "SELECT * FROM projects WHERE project_no = ?",
        (source_project_no,),
    ).fetchone()
    if row is None:
        return

    columns = [col[0] for col in cursor.description or []]
    payload = dict(zip(columns, row))
    payload["project_no"] = target_project_no
    if received_date:
        payload["received_date"] = received_date
    payload["updated_at"] = now_text

    columns = list(payload.keys())
    placeholders = ", ".join("?" for _ in columns)
    cursor.execute(
        f"INSERT OR REPLACE INTO projects ({', '.join(columns)}) VALUES ({placeholders})",
        [payload[column] for column in columns],
    )

    cursor.execute("DELETE FROM project_natures WHERE project_no = ?", (target_project_no,))
    for nature_row in cursor.execute(
        "SELECT nature, created_at FROM project_natures WHERE project_no = ?",
        (source_project_no,),
    ):
        cursor.execute(
            "INSERT OR IGNORE INTO project_natures (project_no, nature, created_at) VALUES (?, ?, ?)",
            (target_project_no, nature_row[0], nature_row[1]),
        )

    cursor.execute("DELETE FROM project_personnel WHERE project_no = ?", (target_project_no,))
    for personnel_row in cursor.execute(
        "SELECT personnel_id, created_at FROM project_personnel WHERE project_no = ?",
        (source_project_no,),
    ):
        cursor.execute(
            "INSERT OR IGNORE INTO project_personnel (project_no, personnel_id, created_at) VALUES (?, ?, ?)",
            (target_project_no, personnel_row[0], personnel_row[1]),
        )


def _merge_project_field_from_split(
    cursor: sqlite3.Cursor,
    base: str,
    split_no: str,
    *,
    now_text: str,
) -> None:
    split_row = cursor.execute(
        "SELECT design_work_path, detail_work_path, local_work_path, received_date FROM projects WHERE project_no = ?",
        (split_no,),
    ).fetchone()
    base_row = cursor.execute(
        "SELECT design_work_path, detail_work_path, local_work_path, received_date FROM projects WHERE project_no = ?",
        (base,),
    ).fetchone()
    if split_row is None or base_row is None:
        return

    design_work_path, detail_work_path, local_work_path, base_received = base_row
    split_design, split_detail, split_local, split_received = split_row

    updates: dict[str, str] = {}
    if not (design_work_path or "").strip() and (split_design or "").strip():
        updates["design_work_path"] = split_design.strip()
    if not (detail_work_path or "").strip() and (split_detail or "").strip():
        updates["detail_work_path"] = split_detail.strip()
    if not (local_work_path or "").strip() and (split_local or "").strip():
        updates["local_work_path"] = split_local.strip()

    base_received = (base_received or "").strip()
    split_received = (split_received or "").strip()
    if split_received and (not base_received or split_received < base_received):
        updates["received_date"] = split_received

    if not updates:
        return

    assignments = ", ".join(f"{field} = ?" for field in updates)
    cursor.execute(
        f"UPDATE projects SET {assignments}, updated_at = ? WHERE project_no = ?",
        [*updates.values(), now_text, base],
    )


def _merge_split_project_into_base(cursor: sqlite3.Cursor, split_no: str, *, now_text: str) -> None:
    split_no = (split_no or "").strip()
    if not is_split_project_no(split_no):
        return

    base = parse_base_project_no(split_no)
    if split_no == base:
        return

    base_exists = cursor.execute(
        "SELECT 1 FROM projects WHERE project_no = ?",
        (base,),
    ).fetchone()
    if not base_exists:
        _rename_project_no(cursor, split_no, base, now_text)
        return

    for contact_form_id, source_type, source_contact_form_id, created_at in cursor.execute(
        """
        SELECT contact_form_id, source_type, source_contact_form_id, created_at
        FROM contact_form_projects
        WHERE project_no = ?
        """,
        (split_no,),
    ):
        cursor.execute(
            """
            INSERT OR IGNORE INTO contact_form_projects (
              contact_form_id, project_no, source_type, source_contact_form_id, created_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (contact_form_id, base, source_type, source_contact_form_id, created_at),
        )
    cursor.execute("DELETE FROM contact_form_projects WHERE project_no = ?", (split_no,))

    for nature_row in cursor.execute(
        "SELECT nature, created_at FROM project_natures WHERE project_no = ?",
        (split_no,),
    ):
        cursor.execute(
            "INSERT OR IGNORE INTO project_natures (project_no, nature, created_at) VALUES (?, ?, ?)",
            (base, nature_row[0], nature_row[1]),
        )
    cursor.execute("DELETE FROM project_natures WHERE project_no = ?", (split_no,))

    for personnel_row in cursor.execute(
        "SELECT personnel_id, created_at FROM project_personnel WHERE project_no = ?",
        (split_no,),
    ):
        cursor.execute(
            "INSERT OR IGNORE INTO project_personnel (project_no, personnel_id, created_at) VALUES (?, ?, ?)",
            (base, personnel_row[0], personnel_row[1]),
        )
    cursor.execute("DELETE FROM project_personnel WHERE project_no = ?", (split_no,))

    cursor.execute(
        "UPDATE contact_form_project_cancellations SET project_no = ? WHERE project_no = ?",
        (base, split_no),
    )

    _merge_project_field_from_split(cursor, base, split_no, now_text=now_text)
    cursor.execute("DELETE FROM projects WHERE project_no = ?", (split_no,))


def migrate_merge_split_projects() -> None:
    """将历史拆分项目合并回基础项目号，多联系单仅保留在 contact_form_projects。"""
    conn = db.engine.raw_connection()
    try:
        cursor = conn.cursor()
        now_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        split_rows = cursor.execute(
            """
            SELECT project_no FROM projects
            WHERE instr(project_no, '~') > 0 OR instr(project_no, '#') > 0
            ORDER BY project_no
            """
        ).fetchall()
        for (split_no,) in split_rows:
            _merge_split_project_into_base(cursor, str(split_no), now_text=now_text)

        orphan_links = cursor.execute(
            """
            SELECT DISTINCT cfp.project_no
            FROM contact_form_projects cfp
            WHERE instr(cfp.project_no, '~') > 0 OR instr(cfp.project_no, '#') > 0
            ORDER BY cfp.project_no
            """
        ).fetchall()
        for (split_no,) in orphan_links:
            base = parse_base_project_no(str(split_no))
            for row in cursor.execute(
                """
                SELECT contact_form_id, source_type, source_contact_form_id, created_at
                FROM contact_form_projects
                WHERE project_no = ?
                """,
                (split_no,),
            ):
                cursor.execute(
                    """
                    INSERT OR IGNORE INTO contact_form_projects (
                      contact_form_id, project_no, source_type, source_contact_form_id, created_at
                    ) VALUES (?, ?, ?, ?, ?)
                    """,
                    (row[0], base, row[1], row[2], row[3]),
                )
            cursor.execute("DELETE FROM contact_form_projects WHERE project_no = ?", (split_no,))

        conn.commit()
    finally:
        conn.close()


def migrate_split_multi_contact_projects() -> None:
    """已废弃：历史迁移占位，合并逻辑见 migrate_merge_split_projects。"""
    return


def _rename_project_no(cursor: sqlite3.Cursor, old_no: str, new_no: str, now_text: str) -> None:
    if old_no == new_no:
        return
    exists = cursor.execute(
        "SELECT 1 FROM projects WHERE project_no = ?",
        (new_no,),
    ).fetchone()
    if exists:
        return

    row = cursor.execute(
        "SELECT * FROM projects WHERE project_no = ?",
        (old_no,),
    ).fetchone()
    if row is None:
        return

    columns = [col[0] for col in cursor.description or []]
    payload = dict(zip(columns, row))
    payload["project_no"] = new_no
    payload["updated_at"] = now_text
    insert_columns = list(payload.keys())
    placeholders = ", ".join("?" for _ in insert_columns)
    cursor.execute(
        f"INSERT OR REPLACE INTO projects ({', '.join(insert_columns)}) VALUES ({placeholders})",
        [payload[column] for column in insert_columns],
    )
    cursor.execute("DELETE FROM projects WHERE project_no = ?", (old_no,))

    for table in ("project_natures", "project_personnel", "contact_form_projects"):
        cursor.execute(
            f"UPDATE {table} SET project_no = ? WHERE project_no = ?",
            (new_no, old_no),
        )

    cursor.execute(
        "UPDATE contact_form_project_cancellations SET project_no = ? WHERE project_no = ?",
        (new_no, old_no),
    )


def migrate_split_project_separator() -> None:
    """将历史拆分项目号中的 # 迁移为 ~，避免 Hash 路由解析失败。"""
    conn = db.engine.raw_connection()
    try:
        cursor = conn.cursor()
        rows = cursor.execute(
            "SELECT project_no FROM projects WHERE instr(project_no, '#') > 0 ORDER BY project_no"
        ).fetchall()
        now_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for (old_no,) in rows:
            base, suffix = str(old_no).split("#", 1)
            if not suffix:
                continue
            new_no = f"{base}~{suffix}"
            _rename_project_no(cursor, str(old_no), new_no, now_text)
        conn.commit()
    finally:
        conn.close()


def _delete_empty_split_projects(cursor: sqlite3.Cursor) -> int:
    rows = cursor.execute(
        """
        SELECT p.project_no
        FROM projects p
        WHERE (p.project_no LIKE '%~%' OR p.project_no LIKE '%#%')
          AND NOT EXISTS (
            SELECT 1
            FROM contact_form_projects cfp
            INNER JOIN contact_forms cf ON cf.id = cfp.contact_form_id AND cf.deleted_at IS NULL
            WHERE cfp.project_no = p.project_no
          )
        ORDER BY p.project_no
        """
    ).fetchall()
    for (project_no,) in rows:
        cursor.execute("DELETE FROM projects WHERE project_no = ?", (project_no,))
    return len(rows)


def _insert_missing_project(
    cursor: sqlite3.Cursor,
    project_no: str,
    *,
    now_text: str,
) -> bool:
    """为 contact_form_projects 中已关联但 projects 缺失的项目号补建记录。"""
    project_no = parse_base_project_no((project_no or "").strip())
    if not project_no:
        return False
    if cursor.execute(
        "SELECT 1 FROM projects WHERE project_no = ?",
        (project_no,),
    ).fetchone():
        return False

    contact_row = cursor.execute(
        """
        SELECT cf.title, IFNULL(cf.received_date, '')
        FROM contact_form_projects cfp
        INNER JOIN contact_forms cf ON cf.id = cfp.contact_form_id AND cf.deleted_at IS NULL
        WHERE cfp.project_no = ? OR cfp.project_no LIKE ? OR cfp.project_no LIKE ?
        ORDER BY cf.received_date, cf.id
        LIMIT 1
        """,
        (project_no, f"{project_no}{PROJECT_SPLIT_SEP}%", f"{project_no}{LEGACY_PROJECT_SPLIT_SEP}%"),
    ).fetchone()
    if contact_row is None:
        return False

    title = (contact_row[0] or "").strip() or project_no
    received_date = (contact_row[1] or "").strip()

    cursor.execute(
        """
        INSERT INTO projects (
          project_no, name, customer, status, design_completed, detail_completed,
          received_date, planned_start_date, planned_end_date,
          actual_start_date, actual_end_date,
          design_work_path, detail_work_path, local_work_path,
          created_at, updated_at
        ) VALUES (?, ?, '', 'active', 0, 0, ?, ?, '', '', '', '', '', '', ?, ?)
        """,
        (project_no, title, received_date, received_date, now_text, now_text),
    )
    return True


def migrate_dedupe_processing_contacts() -> None:
    """同一项目仅保留一张加工单联系单，去除 BRD 与 加工单-{项目号} 重复挂载。"""
    conn = db.engine.raw_connection()
    try:
        cursor = conn.cursor()
        now_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute(
            """
            DELETE FROM contact_form_projects
            WHERE contact_form_id IN (
              SELECT id FROM contact_forms WHERE deleted_at IS NOT NULL
            )
            """
        )

        rows = cursor.execute(
            """
            SELECT cfp.project_no, cfp.contact_form_id
            FROM contact_form_projects cfp
            INNER JOIN contact_forms cf ON cf.id = cfp.contact_form_id AND cf.deleted_at IS NULL
            ORDER BY cfp.project_no, cfp.contact_form_id
            """
        ).fetchall()

        by_project: dict[str, list[str]] = {}
        for project_no, contact_id in rows:
            normalized = str(contact_id or "").strip()
            if is_processing_contact_id(normalized):
                by_project.setdefault(str(project_no), []).append(normalized)

        for project_no, contact_ids in by_project.items():
            if len(contact_ids) <= 1:
                continue
            canonical = f"{PROCESSING_CONTACT_PREFIX}{project_no}"
            prefixed = [cid for cid in contact_ids if cid == canonical]
            keep_id = prefixed[0] if prefixed else sorted(contact_ids)[0]
            for contact_id in contact_ids:
                if contact_id == keep_id:
                    continue
                cursor.execute(
                    "DELETE FROM contact_form_projects WHERE project_no = ? AND contact_form_id = ?",
                    (project_no, contact_id),
                )
                orphan = cursor.execute(
                    "SELECT 1 FROM contact_form_projects WHERE contact_form_id = ? LIMIT 1",
                    (contact_id,),
                ).fetchone()
                if not orphan:
                    cursor.execute(
                        "UPDATE contact_forms SET deleted_at = ? WHERE id = ? AND deleted_at IS NULL",
                        (now_text, contact_id),
                    )
        conn.commit()
    finally:
        conn.close()


def migrate_orphan_contact_projects() -> None:
    """补建仅有联系单关联、缺失 projects 记录的项目，并清理无有效联系单的拆分项目。"""
    conn = db.engine.raw_connection()
    try:
        cursor = conn.cursor()
        now_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        orphan_rows = cursor.execute(
            """
            SELECT DISTINCT parse_base.project_no
            FROM (
              SELECT CASE
                WHEN instr(cfp.project_no, '~') > 0 THEN substr(cfp.project_no, 1, instr(cfp.project_no, '~') - 1)
                WHEN instr(cfp.project_no, '#') > 0 THEN substr(cfp.project_no, 1, instr(cfp.project_no, '#') - 1)
                ELSE cfp.project_no
              END AS project_no
              FROM contact_form_projects cfp
              INNER JOIN contact_forms cf ON cf.id = cfp.contact_form_id AND cf.deleted_at IS NULL
            ) parse_base
            WHERE NOT EXISTS (
              SELECT 1 FROM projects p WHERE p.project_no = parse_base.project_no
            )
            ORDER BY parse_base.project_no
            """
        ).fetchall()

        for (project_no,) in orphan_rows:
            _insert_missing_project(cursor, str(project_no), now_text=now_text)

        _delete_empty_split_projects(cursor)
        conn.commit()
    finally:
        conn.close()


def migrate_shorten_processing_split_project_no() -> None:
    """将拆分项目号中冗长的加工单联系单 ID 后缀统一为「加工单」。"""
    conn = db.engine.raw_connection()
    try:
        cursor = conn.cursor()
        rows = cursor.execute(
            """
            SELECT project_no FROM projects
            WHERE project_no LIKE '%~加工单-%'
            ORDER BY project_no
            """
        ).fetchall()
        now_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for (old_no,) in rows:
            base = parse_base_project_no(str(old_no))
            new_no = f"{base}{PROJECT_SPLIT_SEP}{PROCESSING_CONTACT_LABEL}"
            _rename_project_no(cursor, str(old_no), new_no, now_text)
        conn.commit()
    finally:
        conn.close()


def migrate_project_detail_workflows() -> None:
    inspector = db.inspect(db.engine)
    if "project_detail_workflows" not in inspector.get_table_names():
        s = _str
        db.session.execute(
            text(
                f"""
                CREATE TABLE project_detail_workflows (
                  project_no                {s()} PRIMARY KEY,
                  modeling_status           {s(16)} NOT NULL DEFAULT 'not_started'
                    CHECK (modeling_status IN ('not_started', 'in_progress', 'completed')),
                  drawing_status            {s(16)} NOT NULL DEFAULT 'not_started'
                    CHECK (drawing_status IN ('not_started', 'in_progress', 'completed')),
                  plate_layout_status       {s(16)} NOT NULL DEFAULT 'not_applicable'
                    CHECK (plate_layout_status IN ('not_started', 'in_progress', 'completed', 'not_applicable')),
                  modeling_started_at       {s(32)},
                  modeling_completed_at     {s(32)},
                  drawing_started_at        {s(32)},
                  drawing_completed_at      {s(32)},
                  plate_layout_started_at   {s(32)},
                  plate_layout_completed_at {s(32)},
                  created_at                {s(32)} NOT NULL,
                  updated_at                {s(32)} NOT NULL,
                  FOREIGN KEY (project_no) REFERENCES projects (project_no) ON DELETE CASCADE
                )
                """
            )
        )
        _ensure_index("project_detail_workflows", "idx_pdw_modeling_status", "modeling_status")
        _ensure_index("project_detail_workflows", "idx_pdw_drawing_status", "drawing_status")
        _ensure_index("project_detail_workflows", "idx_pdw_plate_layout_status", "plate_layout_status")
        db.session.commit()

    rows = db.session.execute(
        text(
            """
            SELECT p.project_no, p.detail_completed
            FROM projects p
            WHERE EXISTS (
              SELECT 1 FROM project_natures pn
              WHERE pn.project_no = p.project_no
                AND pn.nature IN ('detail', 'plate_layout')
            )
            AND NOT EXISTS (
              SELECT 1 FROM project_detail_workflows w
              WHERE w.project_no = p.project_no
            )
            """
        )
    ).all()

    now_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for row in rows:
        project_no = row.project_no
        nature_rows = db.session.execute(
            text("SELECT nature FROM project_natures WHERE project_no = :project_no"),
            {"project_no": project_no},
        ).all()
        natures = {item.nature for item in nature_rows}
        has_plate_layout = "plate_layout" in natures
        detail_completed = bool(row.detail_completed)

        if detail_completed:
            db.session.execute(
                text(
                    """
                    INSERT INTO project_detail_workflows (
                      project_no,
                      modeling_status, drawing_status, plate_layout_status,
                      modeling_started_at, modeling_completed_at,
                      drawing_started_at, drawing_completed_at,
                      plate_layout_started_at, plate_layout_completed_at,
                      created_at, updated_at
                    ) VALUES (
                      :project_no,
                      'completed', 'completed', :plate_layout_status,
                      :completed_at, :completed_at,
                      :completed_at, :completed_at,
                      :plate_started, :plate_completed,
                      :now_text, :now_text
                    )
                    """
                ),
                {
                    "project_no": project_no,
                    "plate_layout_status": "completed" if has_plate_layout else "not_applicable",
                    "completed_at": now_text,
                    "plate_started": now_text if has_plate_layout else None,
                    "plate_completed": now_text if has_plate_layout else None,
                    "now_text": now_text,
                },
            )
        else:
            db.session.execute(
                text(
                    """
                    INSERT INTO project_detail_workflows (
                      project_no,
                      modeling_status, drawing_status, plate_layout_status,
                      created_at, updated_at
                    ) VALUES (
                      :project_no,
                      'not_started', 'not_started', :plate_layout_status,
                      :now_text, :now_text
                    )
                    """
                ),
                {
                    "project_no": project_no,
                    "plate_layout_status": "not_started" if has_plate_layout else "not_applicable",
                    "now_text": now_text,
                },
            )

    if rows:
        db.session.commit()


def migrate_project_detail_workflows_model_weight() -> None:
    inspector = db.inspect(db.engine)
    if "project_detail_workflows" not in inspector.get_table_names():
        return

    columns = {col["name"] for col in inspector.get_columns("project_detail_workflows")}
    if "model_weight_tons" not in columns:
        db.session.execute(text("ALTER TABLE project_detail_workflows ADD COLUMN model_weight_tons REAL"))
    if "model_weight_updated_at" not in columns:
        db.session.execute(
            text("ALTER TABLE project_detail_workflows ADD COLUMN model_weight_updated_at TEXT")
        )
    if "model_weight_updated_by" not in columns:
        db.session.execute(
            text("ALTER TABLE project_detail_workflows ADD COLUMN model_weight_updated_by TEXT")
        )
    db.session.commit()


def migrate_project_detail_workflows_plate_layout_enabled() -> None:
    bind = db.session.get_bind()
    if bind.dialect.name != "sqlite":
        return

    inspector = db.inspect(db.engine)
    if "project_detail_workflows" not in inspector.get_table_names():
        return

    columns = {col["name"] for col in inspector.get_columns("project_detail_workflows")}
    if "plate_layout_enabled" not in columns:
        db.session.execute(
            text(
                "ALTER TABLE project_detail_workflows "
                "ADD COLUMN plate_layout_enabled INTEGER NOT NULL DEFAULT 1"
            )
        )
        db.session.commit()

    # 历史「排板」项目性质 → 细化流程开关；仅 plate_layout 无 detail 的项目补写 detail
    db.session.execute(
        text(
            """
            INSERT OR IGNORE INTO project_natures (project_no, nature, created_at)
            SELECT pn.project_no, 'detail', datetime('now', 'localtime')
            FROM project_natures pn
            WHERE pn.nature = 'plate_layout'
              AND NOT EXISTS (
                SELECT 1 FROM project_natures d
                WHERE d.project_no = pn.project_no AND d.nature = 'detail'
              )
            """
        )
    )

    db.session.execute(
        text(
            """
            UPDATE project_detail_workflows
            SET plate_layout_enabled = 1
            """
        )
    )

    db.session.execute(
        text(
            """
            UPDATE project_detail_workflows
            SET plate_layout_status = 'not_started'
            WHERE plate_layout_enabled = 1
              AND plate_layout_status = 'not_applicable'
            """
        )
    )

    db.session.execute(text("DELETE FROM project_natures WHERE nature = 'plate_layout'"))
    db.session.commit()


def migrate_project_design_workflows() -> None:
    inspector = db.inspect(db.engine)
    if "project_design_workflows" not in inspector.get_table_names():
        s = _str
        f = _float_type
        db.session.execute(
            text(
                f"""
                CREATE TABLE project_design_workflows (
                  project_no                {s()} PRIMARY KEY,
                  design_started_at         {s(10)},
                  design_completed_at       {s(10)},
                  design_area_sqm           {f()},
                  design_area_updated_at    {s(32)},
                  design_area_updated_by    {s()},
                  created_at                {s(32)} NOT NULL,
                  updated_at                {s(32)} NOT NULL,
                  FOREIGN KEY (project_no) REFERENCES projects (project_no) ON DELETE CASCADE,
                  FOREIGN KEY (design_area_updated_by) REFERENCES personnel (id)
                )
                """
            )
        )
        db.session.commit()

    rows = db.session.execute(
        text(
            """
            SELECT p.project_no
            FROM projects p
            WHERE EXISTS (
              SELECT 1 FROM project_natures pn
              WHERE pn.project_no = p.project_no
                AND pn.nature = 'design'
            )
            AND NOT EXISTS (
              SELECT 1 FROM project_design_workflows w
              WHERE w.project_no = p.project_no
            )
            """
        )
    ).all()

    now_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for row in rows:
        db.session.add(
            ProjectDesignWorkflow(
                project_no=row.project_no,
                created_at=now_text,
                updated_at=now_text,
            )
        )

    if rows:
        db.session.commit()


def migrate_project_design_workflows_design_area() -> None:
    """为设计流程表补充设计面积字段（SQLite / MySQL 均可）。"""
    inspector = db.inspect(db.engine)
    if "project_design_workflows" not in inspector.get_table_names():
        return

    _ensure_columns(
        "project_design_workflows",
        f"design_area_sqm {_float_type()}",
        f"design_area_updated_at {_str(32)}",
        f"design_area_updated_by {_str()}",
    )


def migrate_project_design_workflows_date_only() -> None:
    """将设计开始/结束从带时分秒规范为仅日期 YYYY-MM-DD。"""
    inspector = db.inspect(db.engine)
    if "project_design_workflows" not in inspector.get_table_names():
        return

    db.session.execute(
        text(
            """
            UPDATE project_design_workflows
            SET design_started_at = SUBSTR(TRIM(design_started_at), 1, 10)
            WHERE design_started_at IS NOT NULL
              AND LENGTH(TRIM(design_started_at)) > 10
            """
        )
    )
    db.session.execute(
        text(
            """
            UPDATE project_design_workflows
            SET design_completed_at = SUBSTR(TRIM(design_completed_at), 1, 10)
            WHERE design_completed_at IS NOT NULL
              AND LENGTH(TRIM(design_completed_at)) > 10
            """
        )
    )
    db.session.commit()


def migrate_contact_form_projects_id() -> None:
    """为 contact_form_projects 补唯一行 id（更新关联时会删除重建）。"""
    inspector = db.inspect(db.engine)
    if "contact_form_projects" not in inspector.get_table_names():
        return

    columns = {col["name"] for col in inspector.get_columns("contact_form_projects")}
    if "id" in columns:
        return

    bind = db.session.get_bind()
    if bind.dialect.name == "sqlite":
        rows = [
            dict(row)
            for row in db.session.execute(text("SELECT * FROM contact_form_projects")).mappings().all()
        ]
        db.session.execute(text("PRAGMA foreign_keys = OFF"))
        db.session.execute(text("DROP TABLE IF EXISTS contact_form_projects_new"))
        db.session.execute(
            text(
                """
                CREATE TABLE contact_form_projects_new (
                  id                      INTEGER PRIMARY KEY AUTOINCREMENT,
                  contact_form_id         TEXT NOT NULL,
                  project_no              TEXT NOT NULL,
                  source_type             TEXT NOT NULL DEFAULT 'own',
                  source_contact_form_id  TEXT,
                  created_at              TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                  UNIQUE (contact_form_id, project_no),
                  FOREIGN KEY (contact_form_id) REFERENCES contact_forms (id) ON DELETE CASCADE,
                  FOREIGN KEY (project_no) REFERENCES projects (project_no) ON DELETE CASCADE,
                  CHECK (source_type IN ('own', 'inherited', 'added', 'cancelled'))
                )
                """
            )
        )
        for row in rows:
            db.session.execute(
                text(
                    """
                    INSERT OR IGNORE INTO contact_form_projects_new (
                      contact_form_id, project_no, source_type, source_contact_form_id, created_at
                    ) VALUES (
                      :contact_form_id, :project_no, :source_type, :source_contact_form_id, :created_at
                    )
                    """
                ),
                {
                    "contact_form_id": row["contact_form_id"],
                    "project_no": row["project_no"],
                    "source_type": row.get("source_type") or "own",
                    "source_contact_form_id": row.get("source_contact_form_id"),
                    "created_at": row.get("created_at")
                    or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                },
            )
        db.session.execute(text("DROP TABLE contact_form_projects"))
        db.session.execute(
            text("ALTER TABLE contact_form_projects_new RENAME TO contact_form_projects")
        )
        db.session.execute(text("PRAGMA foreign_keys = ON"))
        _ensure_index("contact_form_projects", "idx_cfp_contact_form_id", "contact_form_id")
        _ensure_index("contact_form_projects", "idx_cfp_project_no", "project_no")
        db.session.commit()
        return

    db.session.execute(
        text(
            "ALTER TABLE contact_form_projects "
            "ADD COLUMN id INT NOT NULL AUTO_INCREMENT UNIQUE FIRST"
        )
    )
    db.session.execute(text("ALTER TABLE contact_form_projects DROP PRIMARY KEY"))
    db.session.execute(text("ALTER TABLE contact_form_projects ADD PRIMARY KEY (id)"))
    _ensure_index(
        "contact_form_projects",
        "uq_cfp_contact_project",
        "contact_form_id",
        "project_no",
        unique=True,
    )
    _ensure_index("contact_form_projects", "idx_cfp_contact_form_id", "contact_form_id")
    db.session.commit()


def migrate_change_orders_int_id_and_order_no() -> None:
    """旧版 change_orders 以 VARCHAR id 存变更单号；新版改为自增 id + order_no，并回填关联表。"""
    inspector = db.inspect(db.engine)
    if "change_orders" not in inspector.get_table_names():
        return

    columns = {col["name"]: col for col in inspector.get_columns("change_orders")}
    if "order_no" in columns:
        return

    bind = db.session.get_bind()
    is_mysql = bind.dialect.name == "mysql"
    s = _str
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    old_orders = [
        dict(row)
        for row in db.session.execute(text("SELECT * FROM change_orders")).mappings().all()
    ]
    old_projects = []
    if "change_order_projects" in inspector.get_table_names():
        old_projects = [
            dict(row)
            for row in db.session.execute(text("SELECT * FROM change_order_projects")).mappings().all()
        ]
    old_pdfs = []
    if "change_order_pdfs" in inspector.get_table_names():
        old_pdfs = [
            dict(row)
            for row in db.session.execute(text("SELECT * FROM change_order_pdfs")).mappings().all()
        ]

    if is_mysql:
        db.session.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
    else:
        db.session.execute(text("PRAGMA foreign_keys = OFF"))

    db.session.execute(text("DROP TABLE IF EXISTS change_orders_new"))
    db.session.execute(text("DROP TABLE IF EXISTS change_order_projects_new"))
    db.session.execute(text("DROP TABLE IF EXISTS change_order_pdfs_new"))

    pk_id = (
        "INT NOT NULL AUTO_INCREMENT PRIMARY KEY"
        if is_mysql
        else "INTEGER PRIMARY KEY AUTOINCREMENT"
    )
    int_type = "INT" if is_mysql else "INTEGER"
    created_default = "DEFAULT (datetime('now', 'localtime'))" if not is_mysql else ""

    db.session.execute(
        text(
            f"""
            CREATE TABLE change_orders_new (
              id            {pk_id},
              order_no      {s()},
              title         {s(256)} NOT NULL,
              received_date {s(32)} NOT NULL DEFAULT '',
              content       {_long_text()},
              deleted_at    {s(32)},
              created_at    {s(32)} NOT NULL,
              updated_at    {s(32)}
            )
            """
        )
    )
    db.session.execute(
        text(
            f"""
            CREATE TABLE change_order_projects_new (
              id              {pk_id},
              change_order_id {int_type} NOT NULL,
              project_no      {s()} NOT NULL,
              created_at      {s(32)} NOT NULL {created_default},
              UNIQUE (change_order_id, project_no),
              FOREIGN KEY (change_order_id) REFERENCES change_orders_new (id) ON DELETE CASCADE,
              FOREIGN KEY (project_no) REFERENCES projects (project_no) ON DELETE CASCADE
            )
            """
        )
    )
    db.session.execute(
        text(
            f"""
            CREATE TABLE change_order_pdfs_new (
              id                  {s()} PRIMARY KEY,
              change_order_id     {int_type} NOT NULL,
              file_name           {s(256)} NOT NULL,
              file_path           {_long_text()} NOT NULL,
              file_md5            {s(32)},
              file_size           {int_type},
              mime_type           {s(64)} NOT NULL DEFAULT 'application/pdf',
              attachment_type     {s(16)} NOT NULL DEFAULT 'supplement',
              sort_order          {int_type} NOT NULL DEFAULT 0,
              is_current          {int_type} NOT NULL DEFAULT 1,
              original_file_name  {s(256)},
              remark              {_long_text()},
              deleted_at          {s(32)},
              created_at          {s(32)} NOT NULL,
              FOREIGN KEY (change_order_id) REFERENCES change_orders_new (id) ON DELETE CASCADE
            )
            """
        )
    )

    id_map: dict[str, int] = {}
    for row in old_orders:
        old_id = str(row["id"])
        result = db.session.execute(
            text(
                """
                INSERT INTO change_orders_new (
                  order_no, title, received_date, content, deleted_at, created_at, updated_at
                ) VALUES (
                  :order_no, :title, :received_date, :content, :deleted_at, :created_at, :updated_at
                )
                """
            ),
            {
                "order_no": old_id,
                "title": row["title"],
                "received_date": row.get("received_date") or "",
                "content": row.get("content"),
                "deleted_at": row.get("deleted_at"),
                "created_at": row.get("created_at") or now,
                "updated_at": row.get("updated_at") or row.get("created_at") or now,
            },
        )
        new_id = int(result.lastrowid or 0)
        if not new_id:
            mapped = db.session.execute(
                text(
                    "SELECT id FROM change_orders_new WHERE order_no = :order_no ORDER BY id DESC LIMIT 1"
                ),
                {"order_no": old_id},
            ).first()
            new_id = int(mapped.id) if mapped else 0
        id_map[old_id] = new_id

    for row in old_projects:
        old_change_order_id = str(row["change_order_id"])
        new_change_order_id = id_map.get(old_change_order_id)
        if not new_change_order_id:
            continue
        db.session.execute(
            text(
                """
                INSERT INTO change_order_projects_new (change_order_id, project_no, created_at)
                VALUES (:change_order_id, :project_no, :created_at)
                """
            ),
            {
                "change_order_id": new_change_order_id,
                "project_no": row["project_no"],
                "created_at": row.get("created_at") or now,
            },
        )

    for row in old_pdfs:
        old_change_order_id = str(row["change_order_id"])
        new_change_order_id = id_map.get(old_change_order_id)
        if not new_change_order_id:
            continue
        db.session.execute(
            text(
                """
                INSERT INTO change_order_pdfs_new (
                  id, change_order_id, file_name, file_path, file_md5, file_size, mime_type,
                  attachment_type, sort_order, is_current, original_file_name, remark,
                  deleted_at, created_at
                ) VALUES (
                  :id, :change_order_id, :file_name, :file_path, :file_md5, :file_size, :mime_type,
                  :attachment_type, :sort_order, :is_current, :original_file_name, :remark,
                  :deleted_at, :created_at
                )
                """
            ),
            {
                "id": row["id"],
                "change_order_id": new_change_order_id,
                "file_name": row["file_name"],
                "file_path": row["file_path"],
                "file_md5": row.get("file_md5"),
                "file_size": row.get("file_size"),
                "mime_type": row.get("mime_type") or "application/pdf",
                "attachment_type": row.get("attachment_type") or "supplement",
                "sort_order": row.get("sort_order") or 0,
                "is_current": 1 if row.get("is_current") in (None, 1, True, "1") else 0,
                "original_file_name": row.get("original_file_name"),
                "remark": row.get("remark"),
                "deleted_at": row.get("deleted_at"),
                "created_at": row.get("created_at") or now,
            },
        )

    db.session.execute(text("DROP TABLE IF EXISTS change_order_pdfs"))
    db.session.execute(text("DROP TABLE IF EXISTS change_order_projects"))
    db.session.execute(text("DROP TABLE IF EXISTS change_orders"))
    db.session.execute(text("ALTER TABLE change_orders_new RENAME TO change_orders"))
    db.session.execute(text("ALTER TABLE change_order_projects_new RENAME TO change_order_projects"))
    db.session.execute(text("ALTER TABLE change_order_pdfs_new RENAME TO change_order_pdfs"))

    if is_mysql:
        db.session.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
    else:
        db.session.execute(text("PRAGMA foreign_keys = ON"))

    _ensure_index("change_orders", "idx_change_orders_order_no", "order_no")
    _ensure_index("change_orders", "idx_change_orders_deleted_at", "deleted_at")
    _ensure_index("change_order_projects", "idx_cop_change_order_id", "change_order_id")
    _ensure_index("change_order_projects", "idx_cop_project_no", "project_no")
    _ensure_index("change_order_pdfs", "idx_change_order_pdfs_order_id", "change_order_id")
    _ensure_index("change_order_pdfs", "idx_change_order_pdfs_md5", "file_md5")
    _ensure_index("change_order_pdfs", "idx_change_order_pdfs_deleted_at", "deleted_at")
    db.session.commit()


def migrate_change_order_supplements_to_primary() -> None:
    """将变更单附件（supplement）迁移为正文（primary），统一为仅正文文件模型。"""
    inspector = db.inspect(db.engine)
    if "change_order_pdfs" not in inspector.get_table_names():
        return

    columns = {col["name"] for col in inspector.get_columns("change_order_pdfs")}
    if "attachment_type" not in columns:
        return

    result = db.session.execute(
        text("""
            UPDATE change_order_pdfs
            SET attachment_type = 'primary',
                is_current = 1
            WHERE attachment_type = 'supplement'
              AND deleted_at IS NULL
        """)
    )
    if result.rowcount:
        print(f"[migrate] change_order supplements → primary: {result.rowcount} rows")
    db.session.commit()


def migrate_change_order_projects_id() -> None:
    """为 change_order_projects 补唯一行 id；勿用变更单号作主键（更新时会删除重建）。"""
    inspector = db.inspect(db.engine)
    if "change_order_projects" not in inspector.get_table_names():
        return

    columns = {col["name"] for col in inspector.get_columns("change_order_projects")}
    if "id" in columns:
        return


    bind = db.session.get_bind()
    if bind.dialect.name == "sqlite":
        rows = [
            dict(row)
            for row in db.session.execute(text("SELECT * FROM change_order_projects")).mappings().all()
        ]
        db.session.execute(text("PRAGMA foreign_keys = OFF"))
        db.session.execute(text("DROP TABLE IF EXISTS change_order_projects_new"))
        db.session.execute(
            text(
                """
                CREATE TABLE change_order_projects_new (
                  id              INTEGER PRIMARY KEY AUTOINCREMENT,
                  change_order_id INTEGER NOT NULL,
                  project_no      TEXT NOT NULL,
                  created_at      TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                  UNIQUE (change_order_id, project_no),
                  FOREIGN KEY (change_order_id) REFERENCES change_orders (id) ON DELETE CASCADE,
                  FOREIGN KEY (project_no) REFERENCES projects (project_no) ON DELETE CASCADE
                )
                """
            )
        )
        for row in rows:
            db.session.execute(
                text(
                    """
                    INSERT OR IGNORE INTO change_order_projects_new (change_order_id, project_no, created_at)
                    VALUES (:change_order_id, :project_no, :created_at)
                    """
                ),
                {
                    "change_order_id": row["change_order_id"],
                    "project_no": row["project_no"],
                    "created_at": row.get("created_at")
                    or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                },
            )
        db.session.execute(text("DROP TABLE change_order_projects"))
        db.session.execute(
            text("ALTER TABLE change_order_projects_new RENAME TO change_order_projects")
        )
        db.session.execute(text("PRAGMA foreign_keys = ON"))
        _ensure_index("change_order_projects", "idx_cop_change_order_id", "change_order_id")
        _ensure_index("change_order_projects", "idx_cop_project_no", "project_no")
        db.session.commit()
        return

    # MySQL：追加自增 id，再切主键
    db.session.execute(
        text(
            "ALTER TABLE change_order_projects "
            "ADD COLUMN id INT NOT NULL AUTO_INCREMENT UNIQUE FIRST"
        )
    )
    db.session.execute(text("ALTER TABLE change_order_projects DROP PRIMARY KEY"))
    db.session.execute(text("ALTER TABLE change_order_projects ADD PRIMARY KEY (id)"))
    _ensure_index(
        "change_order_projects",
        "uq_cop_order_project",
        "change_order_id",
        "project_no",
        unique=True,
    )
    _ensure_index("change_order_projects", "idx_cop_change_order_id", "change_order_id")
    db.session.commit()


def migrate_role_workshops_table() -> None:
    """为已有数据库补建角色科室关联表。"""
    s = _str
    db.session.execute(
        text(
            f"""
            CREATE TABLE IF NOT EXISTS role_workshops (
              role_id    {s()} NOT NULL,
              workshop   {s(128)} NOT NULL DEFAULT '',
              created_at {s(32)} NOT NULL,
              PRIMARY KEY (role_id, workshop),
              FOREIGN KEY (role_id) REFERENCES roles (id) ON DELETE CASCADE
            )
            """
        )
    )
    _ensure_index("role_workshops", "idx_role_workshops_workshop", "workshop")
    db.session.commit()


def migrate_tags_tables() -> None:
    """为已有数据库补建标签相关表。"""
    s = _str
    db.session.execute(
        text(
            f"""
            CREATE TABLE IF NOT EXISTS tags (
              id          {s()} PRIMARY KEY,
              name        {s(128)} NOT NULL UNIQUE,
              created_at  {s(32)} NOT NULL
            )
            """
        )
    )
    db.session.execute(
        text(
            f"""
            CREATE TABLE IF NOT EXISTS project_tags (
              project_no  {s()} NOT NULL,
              tag_id      {s()} NOT NULL,
              created_at  {s(32)} NOT NULL,
              PRIMARY KEY (project_no, tag_id),
              FOREIGN KEY (project_no) REFERENCES projects (project_no) ON DELETE CASCADE,
              FOREIGN KEY (tag_id) REFERENCES tags (id) ON DELETE CASCADE
            )
            """
        )
    )
    _ensure_index("project_tags", "idx_project_tags_project_no", "project_no")
    _ensure_index("project_tags", "idx_project_tags_tag_id", "tag_id")
    db.session.execute(
        text(
            f"""
            CREATE TABLE IF NOT EXISTS contact_form_tags (
              contact_form_id {s()} NOT NULL,
              tag_id          {s()} NOT NULL,
              created_at      {s(32)} NOT NULL,
              PRIMARY KEY (contact_form_id, tag_id),
              FOREIGN KEY (contact_form_id) REFERENCES contact_forms (id) ON DELETE CASCADE,
              FOREIGN KEY (tag_id) REFERENCES tags (id) ON DELETE CASCADE
            )
            """
        )
    )
    _ensure_index("contact_form_tags", "idx_contact_form_tags_contact", "contact_form_id")
    _ensure_index("contact_form_tags", "idx_contact_form_tags_tag", "tag_id")
    db.session.commit()


def migrate_temp_tasks_tables() -> None:
    """为已有数据库补建临时任务相关表。"""
    s, lt = _str, _long_text
    db.session.execute(
        text(
            f"""
            CREATE TABLE IF NOT EXISTS temp_tasks (
              id            {s()} PRIMARY KEY,
              name          {s(256)} NOT NULL,
              description   {lt()},
              start_time    {s(32)} NOT NULL,
              completed_at  {s(32)},
              is_related_project INTEGER NOT NULL DEFAULT 0,
              related_project_no {s()},
              created_by    {s()} NOT NULL,
              created_at    {s(32)} NOT NULL,
              updated_at    {s(32)} NOT NULL,
              FOREIGN KEY (created_by) REFERENCES personnel (id) ON DELETE CASCADE
            )
            """
        )
    )
    # 兼容老库：补充字段（跨数据库，使用 SQLAlchemy inspector）
    _ensure_columns(
        "temp_tasks",
        "is_related_project INTEGER NOT NULL DEFAULT 0",
        f"related_project_no {s()}",
    )
    _ensure_index("temp_tasks", "idx_temp_tasks_created_by", "created_by")
    _ensure_index("temp_tasks", "idx_temp_tasks_start_time", "start_time")
    db.session.execute(
        text(
            f"""
            CREATE TABLE IF NOT EXISTS temp_task_personnel (
              temp_task_id  {s()} NOT NULL,
              personnel_id  {s()} NOT NULL,
              created_at    {s(32)} NOT NULL,
              PRIMARY KEY (temp_task_id, personnel_id),
              FOREIGN KEY (temp_task_id) REFERENCES temp_tasks (id) ON DELETE CASCADE,
              FOREIGN KEY (personnel_id) REFERENCES personnel (id) ON DELETE CASCADE
            )
            """
        )
    )
    _ensure_index("temp_task_personnel", "idx_temp_task_personnel_personnel", "personnel_id")
    db.session.commit()


def migrate_user_preferences_table() -> None:
    """为已有数据库补建用户偏好表。"""
    s, lt = _str, _long_text
    db.session.execute(
        text(
            f"""
            CREATE TABLE IF NOT EXISTS user_preferences (
              account          {s()} NOT NULL,
              preference_key   {s(128)} NOT NULL,
              preference_value {lt()} NOT NULL,
              updated_at       {s(32)} NOT NULL,
              PRIMARY KEY (account, preference_key)
            )
            """
        )
    )
    _ensure_index("user_preferences", "idx_user_preferences_account", "account")
    db.session.commit()


def migrate_drawing_issue_plans_table() -> None:
    """为已有数据库补建钢构细化发图计划表。"""
    s, lt, f = _str, _long_text, _float_type
    db.session.execute(
        text(
            f"""
            CREATE TABLE IF NOT EXISTS drawing_issue_plans (
              id                  {s(128)} PRIMARY KEY,
              year                INTEGER NOT NULL,
              month               INTEGER NOT NULL,
              seq                 INTEGER NOT NULL,
              project_name        {s(512)} NOT NULL,
              project_no          {s()} NOT NULL,
              component_weight_kg {f()},
              detail_planned_issue_date {s(16)},
              detail_actual_issue_date {s(16)},
              floor_deck_planned_issue_date {s(16)},
              floor_deck_actual_issue_date {s(16)},
              material_prep_list_issue_date {s(16)},
              remark              {lt()},
              created_at          {s(32)} NOT NULL,
              updated_at          {s(32)} NOT NULL
            )
            """
        )
    )
    _ensure_index("drawing_issue_plans", "idx_drawing_issue_plans_year_month", "year", "month")
    _ensure_index("drawing_issue_plans", "idx_drawing_issue_plans_year_month_seq", "year", "month", "seq", unique=True)
    db.session.commit()
    migrate_drawing_issue_plans_actual_issue_date()
    migrate_drawing_issue_plans_material_prep_list_issue_date()
    migrate_drawing_issue_plans_typed_issue_dates()


def migrate_drawing_issue_plans_actual_issue_date() -> None:
    """为钢构发图计划表补 actual_issue_date 字段（跨数据库兼容）。"""
    _ensure_columns("drawing_issue_plans", f"actual_issue_date {_str(16)}")


def migrate_drawing_issue_plans_material_prep_list_issue_date() -> None:
    """为钢构发图计划表补 material_prep_list_issue_date 字段（跨数据库兼容）。"""
    _ensure_columns("drawing_issue_plans", f"material_prep_list_issue_date {_str(16)}")


def migrate_drawing_issue_plans_typed_issue_dates() -> None:
    """细化发图计划：拆分为细化/排楼承板独立发图时间字段，并迁移旧数据。"""
    s = _str
    _ensure_columns(
        "drawing_issue_plans",
        f"detail_planned_issue_date {s(16)}",
        f"detail_actual_issue_date {s(16)}",
        f"floor_deck_planned_issue_date {s(16)}",
        f"floor_deck_actual_issue_date {s(16)}",
    )
    inspector = db.inspect(db.engine)
    columns = {col["name"] for col in inspector.get_columns("drawing_issue_plans")}
    if "planned_issue_date" in columns:
        db.session.execute(
            text(
                """
                UPDATE drawing_issue_plans
                SET detail_planned_issue_date = COALESCE(detail_planned_issue_date, planned_issue_date)
                WHERE detail_planned_issue_date IS NULL OR detail_planned_issue_date = ''
                """
            )
        )
    if "actual_issue_date" in columns:
        db.session.execute(
            text(
                """
                UPDATE drawing_issue_plans
                SET detail_actual_issue_date = COALESCE(detail_actual_issue_date, actual_issue_date)
                WHERE detail_actual_issue_date IS NULL OR detail_actual_issue_date = ''
                """
            )
        )
    db.session.commit()


def migrate_monthly_trainings_content_pdf() -> None:
    """为月度培训表补正文 PDF 字段（跨数据库兼容 SQLite / MySQL）。"""
    inspector = db.inspect(db.engine)
    if "monthly_trainings" not in inspector.get_table_names():
        return
    s, lt = _str, _long_text
    _ensure_columns(
        "monthly_trainings",
        f"content_file_name {s(256)}",
        f"content_file_path {lt()}",
        "content_file_size INTEGER",
        f"content_mime_type {s(64)}",
    )


def migrate_monthly_trainings_archive_and_date() -> None:
    """为月度培训表补档案编号、培训日期字段。"""
    inspector = db.inspect(db.engine)
    if "monthly_trainings" not in inspector.get_table_names():
        return
    s = _str
    _ensure_columns(
        "monthly_trainings",
        f"archive_no {s(64)}",
        f"training_date {s(16)}",
    )


def migrate_design_drawing_issue_plans_table() -> None:
    """为已有数据库补建钢构设计发图计划表。"""
    s, lt, f = _str, _long_text, _float_type
    db.session.execute(
        text(
            f"""
            CREATE TABLE IF NOT EXISTS design_drawing_issue_plans (
              id                  {s(128)} PRIMARY KEY,
              year                INTEGER NOT NULL,
              month               INTEGER NOT NULL,
              seq                 INTEGER NOT NULL,
              project_name        {s(512)} NOT NULL,
              project_no          {s()} NOT NULL,
              component_weight_kg {f()},
              design_planned_issue_date {s(16)},
              design_actual_issue_date {s(16)},
              tile_layout_planned_issue_date {s(16)},
              tile_layout_actual_issue_date {s(16)},
              floor_deck_planned_issue_date {s(16)},
              floor_deck_actual_issue_date {s(16)},
              material_prep_list_issue_date {s(16)},
              remark              {lt()},
              created_at          {s(32)} NOT NULL,
              updated_at          {s(32)} NOT NULL
            )
            """
        )
    )
    _ensure_index("design_drawing_issue_plans", "idx_design_drawing_issue_plans_year_month", "year", "month")
    _ensure_index("design_drawing_issue_plans", "idx_design_drawing_issue_plans_year_month_seq", "year", "month", "seq", unique=True)
    db.session.commit()
    migrate_design_drawing_issue_plans_typed_issue_dates()


def migrate_project_models_table() -> None:
    """为已有数据库补建项目模型表（细化模型 / 甲供模型）。"""
    s, lt, f = _str, _long_text, _float_type
    db.session.execute(
        text(
            f"""
            CREATE TABLE IF NOT EXISTS project_models (
              id                {s(64)} PRIMARY KEY,
              project_no        {s(64)} NOT NULL,
              model_type        {s(32)} NOT NULL,
              name              {s(256)} NOT NULL,
              status            {s(32)} NOT NULL DEFAULT 'not_started',
              model_weight_tons {f()},
              model_path        {lt()},
              remark            {lt()},
              seq               INTEGER NOT NULL DEFAULT 0,
              created_at        {s(32)} NOT NULL,
              updated_at        {s(32)} NOT NULL
            )
            """
        )
    )
    _ensure_index("project_models", "idx_project_models_project_no", "project_no")
    _ensure_index("project_models", "idx_project_models_model_type", "model_type")
    _ensure_index("project_models", "idx_project_models_status", "status")
    _ensure_index(
        "project_models",
        "idx_project_models_project_no_seq",
        "project_no",
        "seq",
    )
    db.session.commit()


def migrate_settlement_tables() -> None:
    """为已有数据库补建钢结构技术科结算相关表。"""
    s, lt, f = _str, _long_text, _float_type
    db.session.execute(
        text(
            f"""
            CREATE TABLE IF NOT EXISTS settlement_pricing_basis (
              id            {s(128)} PRIMARY KEY,
              category      {s(16)} NOT NULL,
              pricing_code  {s(32)} NOT NULL,
              item_name     {s(512)} NOT NULL,
              calc_process  {lt()},
              unit_price    {f()} NOT NULL,
              unit          {s(32)} NOT NULL,
              remark        {lt()},
              seq           INTEGER NOT NULL DEFAULT 0,
              created_at    {s(32)} NOT NULL,
              updated_at    {s(32)} NOT NULL
            )
            """
        )
    )
    _ensure_index("settlement_pricing_basis", "idx_settlement_pricing_category", "category")
    _ensure_index("settlement_pricing_basis", "idx_settlement_pricing_code", "category", "pricing_code", unique=True)

    db.session.execute(
        text(
            f"""
            CREATE TABLE IF NOT EXISTS settlement_records (
              id               {s(128)} PRIMARY KEY,
              year             INTEGER NOT NULL,
              month            INTEGER NOT NULL,
              seq              INTEGER NOT NULL,
              category         {s(16)} NOT NULL,
              name             {s(512)} NOT NULL,
              project_no       {s(64)},
              quantity         {f()} NOT NULL DEFAULT 0,
              unit             {s(32)} NOT NULL DEFAULT '',
              unit_price       {f()} NOT NULL DEFAULT 0,
              total_price      {f()} NOT NULL DEFAULT 0,
              coefficient      {f()} NOT NULL DEFAULT 1,
              pricing_code     {s(32)} NOT NULL DEFAULT '',
              settlement_year  INTEGER,
              settlement_month INTEGER,
              issue_year       INTEGER,
              issue_month      INTEGER,
              created_at       {s(32)} NOT NULL,
              updated_at       {s(32)} NOT NULL
            )
            """
        )
    )
    _ensure_index("settlement_records", "idx_settlement_records_year_month", "year", "month")
    _ensure_index("settlement_records", "idx_settlement_records_category", "category")
    _ensure_index(
        "settlement_records",
        "idx_settlement_records_year_month_category_seq",
        "year",
        "month",
        "category",
        "seq",
        unique=True,
    )

    db.session.execute(
        text(
            f"""
            CREATE TABLE IF NOT EXISTS settlement_pending_items (
              id            {s(128)} PRIMARY KEY,
              category      {s(16)} NOT NULL,
              seq           INTEGER NOT NULL,
              name          {s(512)} NOT NULL,
              project_no    {s(64)},
              quantity      {f()} NOT NULL DEFAULT 0,
              unit          {s(32)} NOT NULL DEFAULT '',
              unit_price    {f()} NOT NULL DEFAULT 0,
              total_price   {f()} NOT NULL DEFAULT 0,
              coefficient   {f()} NOT NULL DEFAULT 1,
              pricing_code  {s(32)} NOT NULL DEFAULT '',
              issue_year    INTEGER,
              issue_month   INTEGER,
              created_at    {s(32)} NOT NULL,
              updated_at    {s(32)} NOT NULL
            )
            """
        )
    )
    _ensure_index("settlement_pending_items", "idx_settlement_pending_category", "category")
    _ensure_index(
        "settlement_pending_items",
        "idx_settlement_pending_category_seq",
        "category",
        "seq",
        unique=True,
    )
    db.session.commit()


def migrate_design_drawing_issue_plans_typed_issue_dates() -> None:
    """设计发图计划：拆分为设计/排瓦/排楼承板独立发图时间，并合并旧 task_type 多行。"""
    s = _str
    _ensure_columns(
        "design_drawing_issue_plans",
        f"design_planned_issue_date {s(16)}",
        f"design_actual_issue_date {s(16)}",
        f"tile_layout_planned_issue_date {s(16)}",
        f"tile_layout_actual_issue_date {s(16)}",
        f"floor_deck_planned_issue_date {s(16)}",
        f"floor_deck_actual_issue_date {s(16)}",
    )

    inspector = db.inspect(db.engine)
    columns = {col["name"] for col in inspector.get_columns("design_drawing_issue_plans")}
    has_task_type = "task_type" in columns
    has_planned = "planned_issue_date" in columns
    has_actual = "actual_issue_date" in columns

    # 无 task_type 的旧单行：把通用日期迁到设计字段
    if has_planned:
        db.session.execute(
            text(
                """
                UPDATE design_drawing_issue_plans
                SET design_planned_issue_date = COALESCE(NULLIF(design_planned_issue_date, ''), planned_issue_date)
                WHERE (design_planned_issue_date IS NULL OR design_planned_issue_date = '')
                  AND planned_issue_date IS NOT NULL AND planned_issue_date != ''
                  AND (
                    task_type IS NULL OR task_type = '' OR task_type = 'design'
                  )
                """
                if has_task_type
                else """
                UPDATE design_drawing_issue_plans
                SET design_planned_issue_date = COALESCE(NULLIF(design_planned_issue_date, ''), planned_issue_date)
                WHERE (design_planned_issue_date IS NULL OR design_planned_issue_date = '')
                  AND planned_issue_date IS NOT NULL AND planned_issue_date != ''
                """
            )
        )
    if has_actual:
        db.session.execute(
            text(
                """
                UPDATE design_drawing_issue_plans
                SET design_actual_issue_date = COALESCE(NULLIF(design_actual_issue_date, ''), actual_issue_date)
                WHERE (design_actual_issue_date IS NULL OR design_actual_issue_date = '')
                  AND actual_issue_date IS NOT NULL AND actual_issue_date != ''
                  AND (
                    task_type IS NULL OR task_type = '' OR task_type = 'design'
                  )
                """
                if has_task_type
                else """
                UPDATE design_drawing_issue_plans
                SET design_actual_issue_date = COALESCE(NULLIF(design_actual_issue_date, ''), actual_issue_date)
                WHERE (design_actual_issue_date IS NULL OR design_actual_issue_date = '')
                  AND actual_issue_date IS NOT NULL AND actual_issue_date != ''
                """
            )
        )

    if has_task_type and has_planned:
        for task_type, planned_col, actual_col in (
            ("tile_layout", "tile_layout_planned_issue_date", "tile_layout_actual_issue_date"),
            ("floor_deck_layout", "floor_deck_planned_issue_date", "floor_deck_actual_issue_date"),
        ):
            db.session.execute(
                text(
                    f"""
                    UPDATE design_drawing_issue_plans
                    SET {planned_col} = COALESCE(NULLIF({planned_col}, ''), planned_issue_date)
                    WHERE task_type = :task_type
                      AND ({planned_col} IS NULL OR {planned_col} = '')
                      AND planned_issue_date IS NOT NULL AND planned_issue_date != ''
                    """
                ),
                {"task_type": task_type},
            )
            if has_actual:
                db.session.execute(
                    text(
                        f"""
                        UPDATE design_drawing_issue_plans
                        SET {actual_col} = COALESCE(NULLIF({actual_col}, ''), actual_issue_date)
                        WHERE task_type = :task_type
                          AND ({actual_col} IS NULL OR {actual_col} = '')
                          AND actual_issue_date IS NOT NULL AND actual_issue_date != ''
                        """
                    ),
                    {"task_type": task_type},
                )

    # 同月同项目多行（旧 task_type）合并为一行
    if has_task_type:
        _merge_design_drawing_issue_plan_task_type_rows()

    db.session.commit()


def _merge_design_drawing_issue_plan_task_type_rows() -> None:
    rows = db.session.execute(text("SELECT * FROM design_drawing_issue_plans")).mappings().all()
    if not rows:
        return

    grouped: dict[tuple[int, int, str], list] = {}
    for row in rows:
        key = (int(row["year"]), int(row["month"]), str(row["project_no"] or "").strip().upper())
        grouped.setdefault(key, []).append(dict(row))

    needs_merge = any(len(items) > 1 for items in grouped.values())
    if not needs_merge:
        return

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.session.execute(text("DELETE FROM design_drawing_issue_plans"))

    for (year, month), month_groups in _group_by_year_month(grouped).items():
        seq = 0
        for project_no, items in month_groups:
            seq += 1
            first = min(items, key=lambda item: int(item.get("seq") or 9999))

            def pick(field: str, task_type: str | None = None) -> str | None:
                for item in items:
                    if task_type is not None and str(item.get("task_type") or "design") != task_type:
                        continue
                    value = item.get(field)
                    if value:
                        return value
                return None

            design_planned = pick("design_planned_issue_date") or pick("planned_issue_date", "design")
            design_actual = pick("design_actual_issue_date") or pick("actual_issue_date", "design")
            tile_planned = pick("tile_layout_planned_issue_date") or pick("planned_issue_date", "tile_layout")
            tile_actual = pick("tile_layout_actual_issue_date") or pick("actual_issue_date", "tile_layout")
            floor_planned = pick("floor_deck_planned_issue_date") or pick(
                "planned_issue_date", "floor_deck_layout"
            )
            floor_actual = pick("floor_deck_actual_issue_date") or pick(
                "actual_issue_date", "floor_deck_layout"
            )

            record_id = f"{year}_{month:02d}_{seq:03d}"
            db.session.execute(
                text(
                    """
                    INSERT INTO design_drawing_issue_plans (
                      id, year, month, seq, project_name, project_no, component_weight_kg,
                      design_planned_issue_date, design_actual_issue_date,
                      tile_layout_planned_issue_date, tile_layout_actual_issue_date,
                      floor_deck_planned_issue_date, floor_deck_actual_issue_date,
                      material_prep_list_issue_date, remark, created_at, updated_at
                    ) VALUES (
                      :id, :year, :month, :seq, :project_name, :project_no, :component_weight_kg,
                      :design_planned, :design_actual,
                      :tile_planned, :tile_actual,
                      :floor_planned, :floor_actual,
                      :prep, :remark, :created_at, :updated_at
                    )
                    """
                ),
                {
                    "id": record_id,
                    "year": year,
                    "month": month,
                    "seq": seq,
                    "project_name": first.get("project_name") or "",
                    "project_no": first.get("project_no") or project_no,
                    "component_weight_kg": first.get("component_weight_kg"),
                    "design_planned": design_planned,
                    "design_actual": design_actual,
                    "tile_planned": tile_planned,
                    "tile_actual": tile_actual,
                    "floor_planned": floor_planned,
                    "floor_actual": floor_actual,
                    "prep": first.get("material_prep_list_issue_date"),
                    "remark": first.get("remark") or "",
                    "created_at": first.get("created_at") or now,
                    "updated_at": now,
                },
            )


def _group_by_year_month(
    grouped: dict[tuple[int, int, str], list],
) -> dict[tuple[int, int], list[tuple[str, list]]]:
    result: dict[tuple[int, int], list[tuple[str, list]]] = {}
    for (year, month, project_no), items in grouped.items():
        result.setdefault((year, month), []).append((project_no, items))
    for key in result:
        result[key].sort(key=lambda item: min(int(row.get("seq") or 9999) for row in item[1]))
    return result


DEFAULT_DRAWING_ISSUE_PLAN_2026_07 = [
    (1, "鑫恒炼钢厂-中频炉平台", "HAB26104", 425000, "2026-06-29", ""),
    (2, "青城铬铁-祷告室", "AC25440", 30000, "2026-07-06", ""),
    (3, "TSI炼铁厂-码头卸料钢构皮带通廊项目", "AC26118", 30000, "2026-07-06", ""),
    (4, "恒丰铝业电解铝项目厂内散装料运输系统斗提间", "HAB26215-1", 266000, "2026-06-25", ""),
    (5, "IRNC镍铁厂抓渣跨-更换钢结构花架", "AC26190", 66000, "2026-07-06", ""),
    (6, "青城铬铁-二平台办公室", "AC26153", 55000, "2026-07-13", ""),
    (7, "鑫恒炼钢厂LF炉", "AC26201", 26700, "2026-07-13", ""),
    (8, "鑫恒炼钢厂-连铸钢平台项目", "AC26103", 200000, "2026-07-20", ""),
    (9, "IRNC公司-阶梯培训会议室", "AC26194", 30000, "2026-07-10", ""),
    (10, "水务中心-水质化验室", "AC26196", 300000, "2026-07-02", ""),
    (11, "IMIP2号消防救援站-车库", "AC26230", 20000, "2026-07-10", ""),
    (12, "鑫恒炼钢厂-炉料、球磨车间", "A26098", 1500000, "2026-07-20", ""),
    (13, "北生活区垃圾房改造项目办公室", "HAC26220", 3747, "2026-07-05", ""),
    (14, "北生活区垃圾房改造", "HAC26221", 7702, "2026-07-05", ""),
    (15, "南生活区垃圾房改造", "HAC26222", 4574, "2026-07-05", ""),
    (16, "TSI炼钢厂-A2转运站", "HAB26156", 136004, "2026-07-05", ""),
    (17, "WESSI高线主厂房烟囱支架钢结构", "AC26218", 10000, "2026-07-05", ""),
]


def seed_default_drawing_issue_plan() -> None:
    """补全 2026 年 7 月钢构发图计划示例数据。"""
    year, month = 2026, 7
    if DrawingIssuePlan.query.filter_by(year=year, month=month).count() > 0:
        return

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for seq, project_name, project_no, weight, planned_date, remark in DEFAULT_DRAWING_ISSUE_PLAN_2026_07:
        record_id = f"{year}_{month:02d}_{seq:03d}"
        db.session.add(
            DrawingIssuePlan(
                id=record_id,
                year=year,
                month=month,
                seq=seq,
                project_name=project_name,
                project_no=project_no,
                component_weight_kg=weight,
                detail_planned_issue_date=planned_date,
                remark=remark,
                created_at=now,
                updated_at=now,
            )
        )
    db.session.commit()


def migrate_project_process_status_from_completion() -> None:
    """按单主任务完成规则修正流程状态（与 project_service 同步逻辑对齐）。"""
    now_date = datetime.now().strftime("%Y-%m-%d")
    now_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    rows = db.session.execute(
        text(
            """
            SELECT
              p.project_no,
              p.status,
              p.design_completed,
              p.detail_completed,
              MAX(CASE WHEN pn.nature = 'design' THEN 1 ELSE 0 END) AS has_design,
              MAX(CASE WHEN pn.nature = 'detail' THEN 1 ELSE 0 END) AS has_detail,
              w.drawing_status,
              w.plate_layout_enabled,
              w.plate_layout_status
            FROM projects p
            LEFT JOIN project_natures pn ON pn.project_no = p.project_no
            LEFT JOIN project_detail_workflows w ON w.project_no = p.project_no
            GROUP BY
              p.project_no,
              p.status,
              p.design_completed,
              p.detail_completed,
              w.drawing_status,
              w.plate_layout_enabled,
              w.plate_layout_status
            """
        )
    ).all()

    for row in rows:
        has_design = bool(row.has_design)
        has_detail = bool(row.has_detail)
        if has_design and has_detail:
            continue

        sync_kind = "design" if has_design else ("detail" if has_detail else None)
        if sync_kind is None:
            continue

        if sync_kind == "design":
            expected_done = bool(row.design_completed)
        elif row.drawing_status == "completed" and (
            not row.plate_layout_enabled or row.plate_layout_status == "completed"
        ):
            expected_done = True
        else:
            expected_done = False

        if expected_done and row.status == "active":
            db.session.execute(
                text(
                    """
                    UPDATE projects
                    SET status = 'done',
                        actual_end_date = CASE
                          WHEN TRIM(IFNULL(actual_end_date, '')) = '' THEN :now_date
                          ELSE actual_end_date
                        END,
                        updated_at = :now_text
                    WHERE project_no = :project_no
                    """
                ),
                {"project_no": row.project_no, "now_date": now_date, "now_text": now_text},
            )
        elif not expected_done and row.status == "done":
            db.session.execute(
                text(
                    """
                    UPDATE projects
                    SET status = 'active',
                        actual_end_date = '',
                        updated_at = :now_text
                    WHERE project_no = :project_no
                    """
                ),
                {"project_no": row.project_no, "now_text": now_text},
            )

    db.session.commit()


def ensure_schema(app: Flask) -> None:
    db.create_all()
    migrate_project_completion_flags()
    migrate_project_structure_and_weight()
    migrate_project_drawing_issue_fields()
    migrate_project_work_paths()
    migrate_project_is_jiagongdan()
    migrate_project_nature_constraint()
    migrate_project_nature_floor_deck_layout()
    migrate_project_detail_workflows()
    migrate_project_detail_workflows_model_weight()
    migrate_project_detail_workflows_plate_layout_enabled()
    migrate_project_design_workflows()
    migrate_project_design_workflows_design_area()
    migrate_project_design_workflows_date_only()
    migrate_project_process_status_from_completion()
    drop_legacy_users_table()

    # 跨数据库兼容的补表/补字段迁移（SQLite / MySQL 均可执行）
    migrate_tags_tables()
    migrate_temp_tasks_tables()
    migrate_user_preferences_table()
    migrate_drawing_issue_plans_table()
    migrate_design_drawing_issue_plans_table()
    migrate_settlement_tables()
    migrate_project_models_table()
    migrate_monthly_trainings_content_pdf()
    migrate_monthly_trainings_archive_and_date()
    migrate_contact_form_relations()  # DDL 跨数据库，数据修复内部自检 SQLite
    migrate_contact_form_projects_id()
    migrate_change_orders_int_id_and_order_no()
    migrate_change_order_supplements_to_primary()
    migrate_change_order_projects_id()
    migrate_role_workshops_table()

    # 以下迁移函数使用 SQLite 专属 API（raw_connection、PRAGMA、cursor），仅 SQLite 下执行
    bind = db.session.get_bind()
    if bind.dialect.name == "sqlite":
        migrate_split_project_separator()
        migrate_shorten_processing_split_project_no()
        migrate_merge_split_projects()
        migrate_dedupe_processing_contacts()
        migrate_orphan_contact_projects()
    migrate_permission_action_constraint()
    migrate_permission_view_all_constraint()
    migrate_dev_team_workshop()
    sync_permission_catalog()
    ensure_system_settings()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    _ensure_detailer_role(now)
    _ensure_detail_team_special_roles(now)
    _ensure_clerk_roles(now)
    _grant_monthly_rest_to_leave_roles(now)
    _grant_production_pages_to_change_order_browse_roles(now)
    db.session.commit()
    # 每月自动为无记录的在职人员补全默认月休（全部周日）
    seed_default_monthly_rest()
    seed_default_drawing_issue_plan()
    try:
        from app.services.settlement_service import seed_settlement_data_if_empty

        seed_settlement_data_if_empty()
    except Exception:
        pass
    # 为无策略的在职人员自动创建默认休假策略（150天/19天，错开起始）
    seed_default_leave_policies()


def seed_if_empty(app: Flask) -> None:
    with app.app_context():
        if Personnel.query.count() > 0:
            return

        default_password = app.config["DEFAULT_LOGIN_PASSWORD"]
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        personnel_samples = [
            {
                "id": "PER001",
                "name": "张三",
                "employee_no": "42601001",
                "team": "设计组",
                "nationality": "中国",
                "workshop": "钢结构技术科",
                "status": "active",
                "created_at": now,
                "updated_at": now,
            },
            {
                "id": "PER009",
                "name": "管理员",
                "employee_no": "42609901",
                "team": "设计组",
                "nationality": "中国",
                "workshop": "钢结构技术科",
                "position": "开发",
                "status": "active",
                "created_at": now,
                "updated_at": now,
            },
        ]

        for item in personnel_samples:
            db.session.add(Personnel(**item))

        all_perm_ids = [row.id for row in Permission.query.all()]

        # 仅在角色不存在时创建（ensure_schema 可能已通过 sync_permission_catalog 创建）
        if Role.query.filter_by(code="admin").first() is None:
            db.session.add(
                Role(
                    id="ROLE001",
                    name="系统管理员",
                    code="admin",
                    description="科室负责人，拥有全部页面权限，含系统设置",
                    status="active",
                    created_at=now,
                    updated_at=now,
                )
            )
            for permission_id in all_perm_ids:
                db.session.add(
                    RolePermission(role_id="ROLE001", permission_id=permission_id, created_at=now)
                )
            db.session.add(
                RolePersonnel(role_id="ROLE001", personnel_id="PER009", created_at=now)
            )

        # 细化工程师角色
        if Role.query.filter_by(code="detailer").first() is None:
            detailer_perm_ids = [
                row.id
                for row in Permission.query.filter(
                    Permission.code.in_(DETAILER_PERMISSION_CODES)
                ).all()
            ]
            db.session.add(
                Role(
                    id="ROLE006",
                    name="细化工程师",
                    code="detailer",
                    description="业务页面仅查看，不可新增或修改",
                    status="active",
                    created_at=now,
                    updated_at=now,
                )
            )
            for permission_id in detailer_perm_ids:
                db.session.add(
                    RolePermission(role_id="ROLE006", permission_id=permission_id, created_at=now)
                )

        db.session.add(
            Project(
                project_no="P2026001",
                name="示例项目",
                customer="张三",
                status="active",
                design_completed=False,
                detail_completed=False,
                received_date="2026-01-01",
                planned_start_date="2026-01-01",
                planned_end_date="2026-06-30",
                created_at=now,
                updated_at=now,
            )
        )
        db.session.add(ProjectNature(project_no="P2026001", nature="design", created_at=now))
        db.session.add(
            ProjectPersonnel(project_no="P2026001", personnel_id="PER001", created_at=now)
        )

        for account in ("admin", "user", "42601001", "42609901"):
            db.session.add(
                AccountPassword(
                    account=account,
                    password=default_password,
                    updated_at=now,
                )
            )

        ensure_system_settings()
        _ensure_detail_team_special_roles(now)
        _ensure_clerk_roles(now)
        db.session.commit()
