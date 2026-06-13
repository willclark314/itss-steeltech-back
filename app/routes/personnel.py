from flask import Blueprint, jsonify, request

from app.services import personnel_service

personnel_bp = Blueprint("personnel", __name__)


@personnel_bp.get("")
def list_personnel():
    keyword = request.args.get("keyword", "")
    status = request.args.get("status", "")
    return jsonify(personnel_service.list_personnel(keyword=keyword, status=status))


@personnel_bp.put("/<personnel_id>")
def update_personnel(personnel_id: str):
    data = request.get_json(silent=True) or {}
    result, error, status = personnel_service.update_personnel(personnel_id, data)
    if error:
        return jsonify({"message": error}), status
    return jsonify(result), status


@personnel_bp.delete("/<personnel_id>")
def delete_personnel(personnel_id: str):
    result, error, status = personnel_service.delete_personnel(personnel_id)
    if error:
        return jsonify({"message": error}), status
    return jsonify(result), status
