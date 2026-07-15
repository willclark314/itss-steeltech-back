from __future__ import annotations

from flask import Blueprint, jsonify, request

from app.services import navigation_config_service
from app.services.permission_service import personnel_has_any_permission
from app.utils.route_permissions import _resolve_personnel_id

navigation_bp = Blueprint("navigation", __name__)


@navigation_bp.route("/navigation-order", methods=["GET"])
def navigation_order():
    personnel_id, error_response = _resolve_personnel_id()
    if error_response:
        return error_response
    if not personnel_id:
        return jsonify({"message": "请先登录"}), 401
    return jsonify(navigation_config_service.get_navigation_order())


@navigation_bp.route("/navigation-order", methods=["PUT"])
def update_navigation_order():
    personnel_id, error_response = _resolve_personnel_id()
    if error_response:
        return error_response
    if not personnel_id:
        return jsonify({"message": "请先登录"}), 401
    if not personnel_has_any_permission(personnel_id, ["page-config:view"]):
        return jsonify({"message": "无权访问该资源"}), 403

    data = request.get_json(silent=True) or {}
    try:
        return jsonify(navigation_config_service.save_navigation_order(data))
    except ValueError as exc:
        return jsonify({"message": str(exc)}), 400
