"""开发环境 SQLite 种子数据，与前端 mock 结构对齐。"""

from __future__ import annotations

import json
import shutil
import sqlite3
from datetime import datetime
from pathlib import Path

from flask import Flask

from app.config import Config
from app.extensions import db
from app.models import (
    AccountPassword,
    Permission,
    Personnel,
    Project,
    ProjectNature,
    ProjectPersonnel,
    Role,
    RolePermission,
    RolePersonnel,
    SystemSetting,
)
from app.services.system_config_service import DEFAULT_LOCAL_WORK_PATH, SETTINGS_KEY
from app.utils.permission_catalog import build_permission_catalog

DEV_USER_PROFILES = {
    "admin": {
        "id": "DEV001",
        "name": "陈魏",
        "employeeNo": "42609901",
        "team": "设计组",
        "position": "钢结构技术副科长",
    },
    "user": {
        "id": "DEV002",
        "name": "杜剑龙",
        "employeeNo": "42609902",
        "team": "设计组",
        "position": "设计工程师",
    },
}


def frontend_db_path() -> Path:
    return Config.BASE_DIR.parent / "itss-steeltech-front" / "server" / "datas" / "steeltech.db"


def bootstrap_sqlite_file(target: Path) -> Path:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        return target

    source = frontend_db_path()
    if source.exists():
        shutil.copy2(source, target)
        return target

    schema_path = Config.BASE_DIR / "datas" / "schema.sql"
    conn = sqlite3.connect(target)
    try:
        conn.executescript(schema_path.read_text(encoding="utf-8"))
        conn.commit()
    finally:
        conn.close()
    return target


def sync_permission_catalog() -> None:
    catalog = build_permission_catalog()
    existing_codes = {code for (code,) in db.session.query(Permission.code).all()}

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for item in catalog:
        if item["code"] in existing_codes:
            continue
        db.session.add(
            Permission(
                id=item["id"],
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

    admin_role = Role.query.filter_by(code="admin").first()
    if admin_role:
        existing_permission_ids = {
            row.permission_id
            for row in RolePermission.query.filter_by(role_id=admin_role.id).all()
        }
        for item in catalog:
            if item["page_key"] == "system-settings" and item["id"] not in existing_permission_ids:
                db.session.add(
                    RolePermission(
                        role_id=admin_role.id,
                        permission_id=item["id"],
                        created_at=now,
                    )
                )

    db.session.commit()


def ensure_system_settings() -> None:
    row = SystemSetting.query.filter_by(key=SETTINGS_KEY).first()
    if row is not None:
        return

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.session.add(
        SystemSetting(
            key=SETTINGS_KEY,
            value=json.dumps(DEFAULT_LOCAL_WORK_PATH.to_dict(), ensure_ascii=False),
            updated_at=now,
        )
    )
    db.session.commit()


def migrate_contact_form_relations() -> None:
    conn = db.engine.raw_connection()
    try:
        cursor = conn.cursor()
        columns = {row[1] for row in cursor.execute("PRAGMA table_info(contact_forms)").fetchall()}
        if "parent_id" not in columns:
            cursor.execute("ALTER TABLE contact_forms ADD COLUMN parent_id TEXT")
        if "root_id" not in columns:
            cursor.execute("ALTER TABLE contact_forms ADD COLUMN root_id TEXT")
        if "relation_type" not in columns:
            cursor.execute(
                "ALTER TABLE contact_forms ADD COLUMN relation_type TEXT NOT NULL DEFAULT 'primary'"
            )
        if "sort_order" not in columns:
            cursor.execute(
                "ALTER TABLE contact_forms ADD COLUMN sort_order INTEGER NOT NULL DEFAULT 0"
            )
        if "cancel_scope" not in columns:
            cursor.execute("ALTER TABLE contact_forms ADD COLUMN cancel_scope TEXT")
        cursor.execute("UPDATE contact_forms SET root_id = id WHERE IFNULL(root_id, '') = ''")
        cursor.execute(
            "UPDATE contact_forms SET relation_type = 'primary' WHERE IFNULL(relation_type, '') = ''"
        )

        project_columns = {
            row[1] for row in cursor.execute("PRAGMA table_info(contact_form_projects)").fetchall()
        }
        if "source_type" not in project_columns:
            cursor.execute(
                "ALTER TABLE contact_form_projects ADD COLUMN source_type TEXT NOT NULL DEFAULT 'own'"
            )
        if "source_contact_form_id" not in project_columns:
            cursor.execute(
                "ALTER TABLE contact_form_projects ADD COLUMN source_contact_form_id TEXT"
            )

        pdf_columns = {row[1] for row in cursor.execute("PRAGMA table_info(contact_form_pdfs)").fetchall()}
        if "attachment_type" not in pdf_columns:
            cursor.execute(
                "ALTER TABLE contact_form_pdfs ADD COLUMN attachment_type TEXT NOT NULL DEFAULT 'supplement'"
            )
        if "remark" not in pdf_columns:
            cursor.execute("ALTER TABLE contact_form_pdfs ADD COLUMN remark TEXT")

        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS contact_form_project_cancellations (
              id                TEXT PRIMARY KEY,
              cancel_contact_id TEXT NOT NULL,
              target_contact_id TEXT NOT NULL,
              project_no        TEXT NOT NULL,
              cancelled_at      TEXT NOT NULL
            )
            """
        )
        conn.commit()
    finally:
        conn.close()


def ensure_schema() -> None:
    db.create_all()
    migrate_contact_form_relations()
    sync_permission_catalog()
    ensure_system_settings()


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
                "name": "陈魏",
                "employee_no": "42609901",
                "team": "设计组",
                "nationality": "中国",
                "workshop": "钢结构技术科",
                "position": "钢结构技术副科长",
                "status": "active",
                "created_at": now,
                "updated_at": now,
            },
        ]

        for item in personnel_samples:
            db.session.add(Personnel(**item))

        all_perm_ids = [row.id for row in Permission.query.all()]
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

        db.session.add(
            Project(
                project_no="P2026001",
                name="示例项目",
                customer="张三",
                status="active",
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
        db.session.commit()
