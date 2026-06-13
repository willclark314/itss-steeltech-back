from flask import Blueprint, jsonify, request

from app.services import project_service
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
