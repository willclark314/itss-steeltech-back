from __future__ import annotations

from steeltech_db.extensions import db
from steeltech_db.models import Permission, Role, RolePermission

from app.services.role_binding_service import get_personnel_role_ids, personnel_has_role_code

ADMIN_ROLE_CODE = "admin"


def get_all_permission_codes() -> list[str]:
    rows = Permission.query.order_by(Permission.code).all()
    return [row.code for row in rows]


def _is_admin_personnel(personnel_id: str) -> bool:
    if not personnel_id:
        return False
    return personnel_has_role_code(personnel_id, ADMIN_ROLE_CODE)


def get_permission_codes_for_role_codes(role_codes: list[str]) -> list[str]:
    normalized = [code.strip() for code in role_codes if (code or "").strip()]
    if not normalized:
        return []
    if ADMIN_ROLE_CODE in normalized:
        return get_all_permission_codes()

    rows = (
        db.session.query(Permission.code)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .join(Role, Role.id == RolePermission.role_id)
        .filter(Role.code.in_(normalized), Role.status == "active")
        .distinct()
        .order_by(Permission.code)
        .all()
    )
    return [row.code for row in rows]


def get_personnel_permission_codes(personnel_id: str) -> list[str]:
    if not personnel_id:
        return []
    if _is_admin_personnel(personnel_id):
        return get_all_permission_codes()

    role_ids = get_personnel_role_ids(personnel_id)
    if not role_ids:
        return []

    rows = (
        db.session.query(Permission.code)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .filter(RolePermission.role_id.in_(role_ids))
        .distinct()
        .order_by(Permission.code)
        .all()
    )
    return [row.code for row in rows]


def personnel_has_permission(personnel_id: str, permission_code: str) -> bool:
    code = (permission_code or "").strip()
    if not code:
        return False
    return code in get_personnel_permission_codes(personnel_id)


def personnel_has_any_permission(personnel_id: str, permission_codes: list[str]) -> bool:
    if not personnel_id:
        return False
    normalized = {code.strip() for code in permission_codes if (code or "").strip()}
    if not normalized:
        return False
    user_codes = set(get_personnel_permission_codes(personnel_id))
    return bool(user_codes & normalized)
