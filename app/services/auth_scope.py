"""JWT 权限解析 — 管理员判定与用户数据范围"""

from __future__ import annotations

from flask_jwt_extended import get_jwt, get_jwt_identity

from steeltech_db.extensions import db
from steeltech_db.models import Personnel, Role, RolePersonnel


def is_dev_account(claims: dict | None = None) -> bool:
    if claims is None:
        try:
            claims = get_jwt()
        except RuntimeError:
            return False
    return claims.get("login_type") == "dev"


def is_dev_admin_account(claims: dict | None = None) -> bool:
    """仅 dev 测试账号 admin 视为管理员；dev 账号 user（杜剑龙等）不算管理员"""
    if claims is None:
        try:
            claims = get_jwt()
        except RuntimeError:
            return False
    if claims.get("login_type") != "dev":
        return False
    return str(get_jwt_identity() or "") == "admin"


def has_admin_role(personnel_id: str) -> bool:
    admin_role = (
        db.session.query(RolePersonnel)
        .join(Role, Role.id == RolePersonnel.role_id)
        .filter(
            RolePersonnel.personnel_id == personnel_id,
            Role.code == "admin",
            Role.status == "active",
        )
        .first()
    )
    return admin_role is not None


def is_jwt_admin() -> bool:
    """当前 JWT 用户是否为管理员（dev admin 账号或拥有 admin 角色）"""
    try:
        claims = get_jwt()
    except RuntimeError:
        return False

    if is_dev_admin_account(claims):
        return True

    # dev 非 admin 账号一律不是管理员
    if is_dev_account(claims):
        return False

    personnel_id = claims.get("personnel_id")
    if not personnel_id:
        return False
    return has_admin_role(str(personnel_id))


def get_user_scope(personnel_id: str) -> dict:
    """
    获取当前用户可编辑/可查看的人员范围。
    返回: { personnelId, role, editablePersonnelIds, team }
    """
    try:
        claims = get_jwt()
    except RuntimeError:
        claims = {}

    person = Personnel.query.get(personnel_id)

    # dev 测试账号 user（杜剑龙等）：强制 member，不受 DB 中误绑 admin 角色影响
    if is_dev_account(claims) and not is_dev_admin_account(claims):
        return {
            "personnelId": personnel_id,
            "role": "member",
            "editablePersonnelIds": [personnel_id] if person else [],
            "team": person.team if person else "",
        }

    if is_jwt_admin():
        all_ids = [p.id for p in Personnel.query.filter_by(status="active").all()]
        return {
            "personnelId": personnel_id,
            "role": "admin",
            "editablePersonnelIds": all_ids,
            "team": person.team if person else "",
        }

    if not person:
        return {
            "personnelId": personnel_id,
            "role": "member",
            "editablePersonnelIds": [],
            "team": "",
        }

    return {
        "personnelId": personnel_id,
        "role": "member",
        "editablePersonnelIds": [personnel_id],
        "team": person.team,
    }
