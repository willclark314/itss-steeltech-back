from flask import Blueprint, jsonify

from app.services import role_service
from app.utils.route_permissions import register_any_permission_guard

permissions_bp = Blueprint("permissions", __name__)

register_any_permission_guard(permissions_bp, "role:view")


@permissions_bp.get("")
def list_permissions():
    return jsonify(role_service.list_permissions())
