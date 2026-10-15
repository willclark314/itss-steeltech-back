from urllib.parse import quote

from flask import Blueprint, Response, jsonify, request

from app.services import personnel_service
from app.utils.route_permissions import register_read_write_guard

personnel_bp = Blueprint("personnel", __name__)

# 有业务页权限即可拉取人员列表做分配/筛选；人员页与导入导出仍需 person:view
register_read_write_guard(
    personnel_bp,
    view_codes=("person:view",),
    read_codes=(
        "person:view",
        "role:view",
        "project:view",
        "project-browse:view",
        "production-project-browse:view",
        "contact:view",
        "contact-browse:view",
        "production-contact:view",
        "design-team-schedule:view",
        "detail-team-schedule:view",
        "leave:view",
        "monthly-rest:view",
        "weekly-meeting:view",
        "director-interview:view",
        "monthly-training:view",
        "my:view",
    ),
    restricted_get_suffixes=("/export-csv",),
)


@personnel_bp.get("")
def list_personnel():
    keyword = request.args.get("keyword", "")
    status = request.args.get("status", "")
    return jsonify(personnel_service.list_personnel(keyword=keyword, status=status))


@personnel_bp.post("")
def create_personnel():
    data = request.get_json(silent=True) or {}
    result, error, status = personnel_service.create_personnel(data)
    if error:
        return jsonify({"message": error}), status
    return jsonify(result), status


@personnel_bp.get("/export-csv")
def export_personnel_csv():
    try:
        csv_bytes = personnel_service.export_personnel_csv_template()
    except Exception as exc:
        return jsonify({"message": f"生成 CSV 失败: {exc}"}), 500

    filename = "人员导入模板.csv"
    return Response(
        csv_bytes,
        mimetype="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename, safe='')}",
        },
    )


@personnel_bp.post("/import-csv")
def import_personnel_csv():
    upload = request.files.get("file")
    if upload is None:
        return jsonify({"message": "请上传 CSV 文件"}), 400

    try:
        file_bytes = upload.read()
    except Exception as exc:
        return jsonify({"message": f"读取文件失败: {exc}"}), 400

    result, error, status = personnel_service.import_personnel_csv(file_bytes)
    if error:
        return jsonify({"message": error}), status
    return jsonify(result), status


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
