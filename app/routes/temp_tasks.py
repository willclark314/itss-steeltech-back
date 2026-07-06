"""临时任务 API 路由"""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from app.services import temp_task_service

temp_tasks_bp = Blueprint("temp_tasks", __name__)


@temp_tasks_bp.get("")
@jwt_required()
def list_temp_tasks():
    result, error, status = temp_task_service.list_temp_tasks(
        personnel_id=request.args.get("personnelId", ""),
    )
    if error:
        return jsonify({"message": error}), status
    return jsonify(result)


@temp_tasks_bp.post("")
@jwt_required()
def create_temp_task():
    data = request.get_json(silent=True) or {}
    result, error, status = temp_task_service.create_temp_task(data)
    if error:
        return jsonify({"message": error}), status
    return jsonify(result), status


@temp_tasks_bp.put("/<task_id>")
@jwt_required()
def update_temp_task(task_id: str):
    data = request.get_json(silent=True) or {}
    result, error, status = temp_task_service.update_temp_task(task_id, data)
    if error:
        return jsonify({"message": error}), status
    return jsonify(result)


@temp_tasks_bp.delete("/<task_id>")
@jwt_required()
def delete_temp_task(task_id: str):
    result, error, status = temp_task_service.delete_temp_task(task_id)
    if error:
        return jsonify({"message": error}), status
    return jsonify(result)
