from flask import Blueprint, jsonify, request

from app.services import tag_service

tags_bp = Blueprint("tags", __name__)


@tags_bp.get("")
def list_tags():
    return jsonify(tag_service.list_tags())


@tags_bp.post("")
def create_tag():
    payload = request.get_json(silent=True) or {}
    name = str(payload.get("name", "")).strip()
    if not name:
        return jsonify({"message": "标签名称不能为空"}), 400
    try:
        tag = tag_service.create_tag(name)
    except ValueError as exc:
        return jsonify({"message": str(exc)}), 400
    return jsonify(tag), 201
