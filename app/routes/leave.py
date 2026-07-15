"""休假管理 API 路由"""

from __future__ import annotations

from typing import Optional

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from app.services import leave_service
from app.services.auth_scope import is_jwt_admin
from app.utils.route_permissions import register_any_permission_guard

leave_bp = Blueprint("leave", __name__)

register_any_permission_guard(leave_bp, "leave:view")


def _get_personnel_id_from_token() -> Optional[str]:
    from flask_jwt_extended import get_jwt

    try:
        claims = get_jwt()
        return claims.get("personnel_id")
    except RuntimeError:
        return None


def _check_is_admin() -> bool:
    return is_jwt_admin()


def _viewer_context() -> tuple[Optional[str], bool]:
    return _get_personnel_id_from_token(), _check_is_admin()


# ════════════════════════════════════════════
#  策略
# ════════════════════════════════════════════


@leave_bp.get("/policies")
@jwt_required()
def list_policies():
    viewer_personnel_id, viewer_is_admin = _viewer_context()
    return jsonify(
        leave_service.list_policies(
            viewer_personnel_id=viewer_personnel_id,
            viewer_is_admin=viewer_is_admin,
        )
    )


@leave_bp.get("/policies/<policy_id>")
@jwt_required()
def get_policy(policy_id: str):
    result = leave_service.get_policy(policy_id)
    if result is None:
        return jsonify({"message": "策略不存在"}), 404

    viewer_personnel_id, viewer_is_admin = _viewer_context()
    if not viewer_is_admin and result.get("personnelId") != viewer_personnel_id:
        return jsonify({"message": "无权限查看该策略"}), 403
    return jsonify(result)


@leave_bp.post("/policies")
@jwt_required()
def save_policy():
    data = request.get_json(silent=True) or {}
    editor_personnel_id, editor_is_admin = _viewer_context()
    result, error, status = leave_service.save_policy(
        data,
        editor_personnel_id=editor_personnel_id,
        editor_is_admin=editor_is_admin,
    )
    if error:
        return jsonify({"message": error}), status
    return jsonify(result), status


@leave_bp.put("/policies/<policy_id>")
@jwt_required()
def update_policy(policy_id: str):
    data = request.get_json(silent=True) or {}
    data["id"] = policy_id
    editor_personnel_id, editor_is_admin = _viewer_context()
    result, error, status = leave_service.save_policy(
        data,
        editor_personnel_id=editor_personnel_id,
        editor_is_admin=editor_is_admin,
    )
    if error:
        return jsonify({"message": error}), status
    return jsonify(result), status


@leave_bp.delete("/policies/<policy_id>")
@jwt_required()
def delete_policy(policy_id: str):
    result = leave_service.get_policy(policy_id)
    if result is None:
        return jsonify({"message": "策略不存在"}), 404

    viewer_personnel_id, viewer_is_admin = _viewer_context()
    if not viewer_is_admin and result.get("personnelId") != viewer_personnel_id:
        return jsonify({"message": "无权限删除该策略"}), 403

    deleted, error, status = leave_service.delete_policy(policy_id)
    if error:
        return jsonify({"message": error}), status
    return jsonify(deleted), status


# ════════════════════════════════════════════
#  休假记录
# ════════════════════════════════════════════


@leave_bp.get("/entries")
@jwt_required()
def list_entries():
    year_str = request.args.get("year")
    year = int(year_str) if year_str else None
    personnel_id = request.args.get("personnelId") or None
    entry_type = request.args.get("type") or None
    status = request.args.get("status") or None
    viewer_personnel_id, viewer_is_admin = _viewer_context()
    return jsonify(
        leave_service.list_entries(
            year=year,
            personnel_id=personnel_id,
            entry_type=entry_type,
            status=status,
            viewer_personnel_id=viewer_personnel_id,
            viewer_is_admin=viewer_is_admin,
        )
    )


@leave_bp.get("/entries/<entry_id>")
@jwt_required()
def get_entry(entry_id: str):
    result = leave_service.get_entry(entry_id)
    if result is None:
        return jsonify({"message": "休假记录不存在"}), 404

    viewer_personnel_id, viewer_is_admin = _viewer_context()
    if not viewer_is_admin and result.get("personnelId") != viewer_personnel_id:
        return jsonify({"message": "无权限查看该记录"}), 403
    return jsonify(result)


@leave_bp.post("/entries")
@jwt_required()
def save_entry():
    data = request.get_json(silent=True) or {}
    editor_personnel_id, editor_is_admin = _viewer_context()
    result, error, status = leave_service.save_entry(
        data,
        editor_personnel_id=editor_personnel_id,
        editor_is_admin=editor_is_admin,
    )
    if error:
        return jsonify({"message": error}), status
    return jsonify(result), status


@leave_bp.put("/entries/<entry_id>")
@jwt_required()
def update_entry(entry_id: str):
    data = request.get_json(silent=True) or {}
    data["id"] = entry_id
    editor_personnel_id, editor_is_admin = _viewer_context()
    result, error, status = leave_service.save_entry(
        data,
        editor_personnel_id=editor_personnel_id,
        editor_is_admin=editor_is_admin,
    )
    if error:
        return jsonify({"message": error}), status
    return jsonify(result), status


@leave_bp.post("/entries/<entry_id>/cancel")
@jwt_required()
def cancel_entry(entry_id: str):
    editor_personnel_id, editor_is_admin = _viewer_context()
    result, error, status = leave_service.cancel_entry(
        entry_id,
        editor_personnel_id=editor_personnel_id,
        editor_is_admin=editor_is_admin,
    )
    if error:
        return jsonify({"message": error}), status
    return jsonify(result), status


@leave_bp.delete("/entries/<entry_id>")
@jwt_required()
def delete_entry(entry_id: str):
    editor_personnel_id, editor_is_admin = _viewer_context()
    result, error, status = leave_service.delete_entry(
        entry_id,
        editor_personnel_id=editor_personnel_id,
        editor_is_admin=editor_is_admin,
    )
    if error:
        return jsonify({"message": error}), status
    return jsonify(result), status


# ════════════════════════════════════════════
#  可见范围
# ════════════════════════════════════════════


@leave_bp.get("/my-scope")
@jwt_required()
def my_scope():
    """返回当前用户的休假数据可见范围"""
    from app.services.auth_scope import get_user_scope

    personnel_id = _get_personnel_id_from_token()
    if not personnel_id:
        return jsonify({"message": "无法识别当前用户"}), 401
    return jsonify(get_user_scope(personnel_id))


# ════════════════════════════════════════════
#  日历聚合
# ════════════════════════════════════════════


@leave_bp.get("/my-calendar")
@jwt_required()
def get_my_calendar():
    """普通员工专用：仅返回本人休假日历，无法获取全员数据"""
    year_str = request.args.get("year")
    year = int(year_str) if year_str else None
    viewer_personnel_id, viewer_is_admin = _viewer_context()

    if viewer_is_admin:
        return jsonify({"message": "管理员请使用 /calendar"}), 400
    if not viewer_personnel_id:
        return jsonify({"message": "无法识别当前用户"}), 401

    return jsonify(
        leave_service.get_calendar(
            year=year,
            viewer_personnel_id=viewer_personnel_id,
            viewer_is_admin=False,
            include_computed=True,
        )
    )


@leave_bp.get("/calendar")
@jwt_required()
def get_calendar():
    year_str = request.args.get("year")
    year = int(year_str) if year_str else None
    requested_personnel_id = (request.args.get("personnelId") or "").strip() or None
    viewer_personnel_id, viewer_is_admin = _viewer_context()

    if not viewer_is_admin:
        if not viewer_personnel_id:
            return jsonify({"message": "无法识别当前用户"}), 401
        if requested_personnel_id and requested_personnel_id != viewer_personnel_id:
            return jsonify({"message": "无权限查看他人员工的休假数据"}), 403

    return jsonify(
        leave_service.get_calendar(
            year=year,
            viewer_personnel_id=viewer_personnel_id,
            viewer_is_admin=viewer_is_admin,
        )
    )
