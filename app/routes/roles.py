from flask import Blueprint, jsonify, request

from app.services import role_service

roles_bp = Blueprint("roles", __name__)


@roles_bp.get("")
def list_roles():
    keyword = request.args.get("keyword", "")
    status = request.args.get("status", "")
    return jsonify(role_service.list_roles(keyword=keyword, status=status))


@roles_bp.post("")
def create_role():
    data = request.get_json(silent=True) or {}
    result, error, status = role_service.create_role(data)
    if error:
        return jsonify({"message": error}), status
    return jsonify(result), status


@roles_bp.put("/<role_id>")
def update_role(role_id: str):
    data = request.get_json(silent=True) or {}
    result, error, status = role_service.update_role(role_id, data)
    if error:
        return jsonify({"message": error}), status
    return jsonify(result), status


@roles_bp.delete("/<role_id>")
def delete_role(role_id: str):
    result, error, status = role_service.delete_role(role_id)
    if error:
        return jsonify({"message": error}), status
    return jsonify(result), status
