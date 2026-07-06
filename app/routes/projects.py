from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt, jwt_required

from app.services import project_service, tag_service
from app.services.auth_scope import is_jwt_admin
from app.utils.pagination import parse_list_page_query

projects_bp = Blueprint("projects", __name__)


@projects_bp.get("/check")
def check_projects():
    raw = (request.args.get("nos") or "").strip()
    project_nos = list(dict.fromkeys(item.strip() for item in raw.split(",") if item.strip()))
    return jsonify(project_service.check_project_nos(project_nos))


@projects_bp.get("")
def list_projects():
    page_query = parse_list_page_query(request.args)
    load_all = request.args.get("all") == "true"
    result = project_service.list_projects(
        keyword=request.args.get("keyword", ""),
        status=request.args.get("status", ""),
        assigned_personnel_id=request.args.get("assignedPersonnelId", ""),
        tag_ids=tag_service.parse_tags_param(request.args.get("tags", "")),
        page_query=page_query,
        load_all=load_all,
    )
    return jsonify(result)


@projects_bp.post("")
def create_project():
    data = request.get_json(silent=True) or {}
    result, error, status = project_service.create_project(data)
    if error:
        return jsonify({"message": error}), status
    return jsonify(result), status


@projects_bp.put("/<path:project_no>")
def update_project(project_no: str):
    data = request.get_json(silent=True) or {}
    result, error, status = project_service.update_project(project_no, data)
    if error:
        return jsonify({"message": error}), status
    return jsonify(result), status


@projects_bp.delete("/<path:project_no>")
def delete_project(project_no: str):
    deleted = project_service.delete_project(project_no)
    if not deleted:
        return jsonify({"message": "项目不存在"}), 404
    return jsonify({"ok": True})


@projects_bp.put("/<path:project_no>/detail-workflow")
def put_detail_workflow(project_no: str):
    data = request.get_json(silent=True) or {}
    result, error, status = project_service.save_detail_workflow(project_no, data)
    if error:
        return jsonify({"message": error}), status
    return jsonify(result), status


@projects_bp.put("/<path:project_no>/detail-workflow/model-weight")
def put_model_weight(project_no: str):
    data = request.get_json(silent=True) or {}
    result, error, status = project_service.save_model_weight(project_no, data)
    if error:
        return jsonify({"message": error}), status
    return jsonify(result), status


@projects_bp.patch("/<path:project_no>/detail-workflow")
def patch_detail_workflow(project_no: str):
    data = request.get_json(silent=True) or {}
    action = (data.get("action") or "").strip()
    if not action:
        return jsonify({"message": "请指定细化流程操作"}), 400
    result, error, status = project_service.apply_detail_workflow_action(project_no, action)
    if error:
        return jsonify({"message": error}), status
    return jsonify(result), status


@projects_bp.post("/<path:project_no>/leave-assignment")
@jwt_required()
def leave_project_assignment(project_no: str):
    data = request.get_json(silent=True) or {}
    claims = get_jwt()
    editor_personnel_id = (claims.get("personnel_id") or "").strip() or None
    target_personnel_id = (data.get("personnelId") or editor_personnel_id or "").strip()
    result, error, status = project_service.leave_project_assignment(
        project_no,
        target_personnel_id=target_personnel_id,
        editor_personnel_id=editor_personnel_id,
        editor_is_admin=is_jwt_admin(),
    )
    if error:
        return jsonify({"message": error}), status
    return jsonify(result)
