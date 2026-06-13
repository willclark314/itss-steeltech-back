from flask import Blueprint, jsonify

from app.services import role_service

permissions_bp = Blueprint("permissions", __name__)


@permissions_bp.get("")
def list_permissions():
    return jsonify(role_service.list_permissions())
