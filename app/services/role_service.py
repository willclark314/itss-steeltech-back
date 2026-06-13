from __future__ import annotations

from sqlalchemy import text

from app.extensions import db
from app.models import Permission, Personnel, Role, RolePermission, RolePersonnel


from app.utils.permission_catalog import sort_permissions


def get_role_permissions(role_id: str) -> list[dict]:
    rows = (
        db.session.query(Permission)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .filter(RolePermission.role_id == role_id)
        .all()
    )
    return sort_permissions([row.to_dict() for row in rows])


def get_role_personnel(role_id: str) -> list[dict]:
    rows = (
        db.session.query(Personnel)
        .join(RolePersonnel, RolePersonnel.personnel_id == Personnel.id)
        .filter(RolePersonnel.role_id == role_id)
        .order_by(Personnel.team, Personnel.name)
        .all()
    )
    return [{"id": row.id, "name": row.name, "team": row.team} for row in rows]


def map_role(row: Role) -> dict:
    permissions = get_role_permissions(row.id)
    assigned = get_role_personnel(row.id)
    return {
        "id": row.id,
        "name": row.name,
        "code": row.code,
        "description": row.description or "",
        "status": row.status,
        "permissionIds": [item["id"] for item in permissions],
        "permissions": permissions,
        "assignedPersonnelIds": [item["id"] for item in assigned],
        "assignedPersonnel": assigned,
    }


def list_permissions() -> list[dict]:
    rows = Permission.query.all()
    return sort_permissions([row.to_dict() for row in rows])


def list_roles(*, keyword: str = "", status: str = "") -> list[dict]:
    keyword = keyword.strip().lower()
    rows = Role.query.order_by(Role.id).all()
    result: list[dict] = []
    for row in rows:
        item = map_role(row)
        if status and item["status"] != status:
            continue
        if keyword:
            searchable = " ".join(
                [
                    item["id"],
                    item["name"],
                    item["code"],
                    item["description"],
                    *[
                        f"{permission['name']} {permission['code']}"
                        for permission in item["permissions"]
                    ],
                    *[
                        f"{person['name']} {person['team']}"
                        for person in item["assignedPersonnel"]
                    ],
                ]
            ).lower()
            if keyword not in searchable:
                continue
        result.append(item)
    return result


def normalize_permission_ids(ids: list[str] | None) -> tuple[list[str] | None, str | None]:
    unique = list(dict.fromkeys(item.strip() for item in (ids or []) if item and item.strip()))
    for permission_id in unique:
        if Permission.query.get(permission_id) is None:
            return None, "权限不存在"
    return unique, None


def normalize_assigned_personnel_ids(ids: list[str] | None) -> tuple[list[str] | None, str | None]:
    unique = list(dict.fromkeys(item.strip() for item in (ids or []) if item and item.strip()))
    for personnel_id in unique:
        if Personnel.query.get(personnel_id) is None:
            return None, "关联人员不存在"
    return unique, None


def sync_role_permissions(role_id: str, permission_ids: list[str]) -> None:
    db.session.execute(
        text("DELETE FROM role_permissions WHERE role_id = :role_id"),
        {"role_id": role_id},
    )
    for permission_id in permission_ids:
        db.session.execute(
            text(
                "INSERT OR IGNORE INTO role_permissions (role_id, permission_id, created_at) "
                "VALUES (:role_id, :permission_id, datetime('now', 'localtime'))"
            ),
            {"role_id": role_id, "permission_id": permission_id},
        )


def sync_role_personnel(role_id: str, personnel_ids: list[str]) -> None:
    db.session.execute(
        text("DELETE FROM role_personnel WHERE role_id = :role_id"),
        {"role_id": role_id},
    )
    for personnel_id in personnel_ids:
        db.session.execute(
            text(
                "INSERT OR IGNORE INTO role_personnel (role_id, personnel_id, created_at) "
                "VALUES (:role_id, :personnel_id, datetime('now', 'localtime'))"
            ),
            {"role_id": role_id, "personnel_id": personnel_id},
        )


def generate_role_id() -> str:
    rows = (
        Role.query.filter(Role.id.like("ROLE%"))
        .order_by(Role.id.desc())
        .limit(1)
        .all()
    )
    if not rows:
        return "ROLE001"
    last = rows[0].id.replace("ROLE", "")
    try:
        number = int(last) + 1
    except ValueError:
        number = 1
    return f"ROLE{number:03d}"


def create_role(payload: dict) -> tuple[dict | None, str | None, int]:
    name = (payload.get("name") or "").strip()
    code = (payload.get("code") or "").strip()
    if not name:
        return None, "角色名称不能为空", 400
    if not code:
        return None, "角色编码不能为空", 400
    if Role.query.filter_by(code=code).first():
        return None, f"角色编码 {code} 已存在", 409

    permission_ids, permission_error = normalize_permission_ids(payload.get("permissionIds"))
    if permission_error:
        return None, permission_error, 400

    personnel_ids, personnel_error = normalize_assigned_personnel_ids(
        payload.get("assignedPersonnelIds")
    )
    if personnel_error:
        return None, personnel_error, 400

    role_id = (payload.get("id") or "").strip() or generate_role_id()
    if Role.query.get(role_id):
        return None, f"角色 {role_id} 已存在", 409

    role = Role(
        id=role_id,
        name=name,
        code=code,
        description=(payload.get("description") or "").strip(),
        status=(payload.get("status") or "").strip() or "active",
    )
    db.session.add(role)
    sync_role_permissions(role_id, permission_ids or [])
    sync_role_personnel(role_id, personnel_ids or [])
    db.session.commit()
    return map_role(role), None, 201


def update_role(role_id: str, payload: dict) -> tuple[dict | None, str | None, int]:
    role = Role.query.get(role_id)
    if role is None:
        return None, "角色不存在", 404

    name = (payload.get("name") or "").strip()
    code = (payload.get("code") or "").strip()
    if not name:
        return None, "角色名称不能为空", 400
    if not code:
        return None, "角色编码不能为空", 400

    duplicate = Role.query.filter(Role.code == code, Role.id != role_id).first()
    if duplicate:
        return None, f"角色编码 {code} 已存在", 409

    permission_ids, permission_error = normalize_permission_ids(
        payload.get("permissionIds") or [item["id"] for item in get_role_permissions(role_id)]
    )
    if permission_error:
        return None, permission_error, 400

    personnel_ids, personnel_error = normalize_assigned_personnel_ids(
        payload.get("assignedPersonnelIds")
        or [item["id"] for item in get_role_personnel(role_id)]
    )
    if personnel_error:
        return None, personnel_error, 400

    role.name = name
    role.code = code
    role.description = (payload.get("description") or "").strip()
    role.status = (payload.get("status") or "").strip() or role.status
    sync_role_permissions(role_id, permission_ids or [])
    sync_role_personnel(role_id, personnel_ids or [])
    db.session.commit()
    return map_role(role), None, 200


def delete_role(role_id: str) -> tuple[dict | None, str | None, int]:
    role = Role.query.get(role_id)
    if role is None:
        return None, "角色不存在", 404
    db.session.delete(role)
    db.session.commit()
    return {"id": role_id}, None, 200
