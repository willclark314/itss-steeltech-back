"""项目模型管理 API"""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from app.services import project_model_service
from app.utils.route_permissions import register_any_permission_guard

project_models_bp = Blueprint("project_models", __name__)

register_any_permission_guard(project_models_bp, "project-model:view")


@project_models_bp.get("")
def list_project_models():
    try:
        page = int(request.args.get("page") or 1)
        page_size = int(request.args.get("pageSize") or 20)
    except (TypeError, ValueError):
        return jsonify({"message": "page / pageSize 必须为整数"}), 400

    try:
        result = project_model_service.list_project_models(
            keyword=request.args.get("keyword") or "",
            model_type=request.args.get("modelType") or "",
            status=request.args.get("status") or "",
            project_no=request.args.get("projectNo") or "",
            page=page,
            page_size=page_size,
        )
    except ValueError as exc:
        return jsonify({"message": str(exc)}), 400
    return jsonify(result)


@project_models_bp.get("/<model_id>")
def get_project_model(model_id: str):
    result = project_model_service.get_project_model(model_id)
    if not result:
        return jsonify({"message": "项目模型不存在"}), 404
    return jsonify(result)


@project_models_bp.post("")
@jwt_required()
def create_project_model():
    payload = request.get_json(silent=True) or {}
    try:
        result = project_model_service.create_project_model(payload)
    except ValueError as exc:
        return jsonify({"message": str(exc)}), 400
    return jsonify(result), 201


@project_models_bp.put("/<model_id>")
@jwt_required()
def update_project_model(model_id: str):
    payload = request.get_json(silent=True) or {}
    result, error, status = project_model_service.update_project_model(model_id, payload)
    if error:
        return jsonify({"message": error}), status
    return jsonify(result), status


@project_models_bp.delete("/<model_id>")
@jwt_required()
def delete_project_model(model_id: str):
    ok, error, status = project_model_service.delete_project_model(model_id)
    if error:
        return jsonify({"message": error}), status
    return jsonify({"ok": ok}), status
