from urllib.parse import quote

from flask import Blueprint, Response, jsonify, request

from app.services import director_interview_service

director_interview_bp = Blueprint("director_interview", __name__)


@director_interview_bp.get("")
def list_interviews():
    year = request.args.get("year", "")
    month = request.args.get("month", "")
    keyword = request.args.get("keyword", "")
    result = director_interview_service.list_interviews(year=year, month=month, keyword=keyword)
    return jsonify(result)


@director_interview_bp.get("/<interview_id>")
def get_interview(interview_id: str):
    interview = director_interview_service.get_interview(interview_id)
    if not interview:
        return jsonify({"message": "约谈记录不存在"}), 404
    return jsonify(interview)


@director_interview_bp.post("")
def create_interview():
    payload = request.get_json(silent=True) or {}
    interview_date = str(payload.get("interviewDate", "")).strip()
    employee_name = str(payload.get("employeeName", "")).strip()
    if not interview_date or not employee_name:
        return jsonify({"message": "约谈日期和员工姓名不能为空"}), 400
    interview = director_interview_service.create_interview(payload)
    return jsonify(interview), 201


@director_interview_bp.put("/<interview_id>")
def update_interview(interview_id: str):
    payload = request.get_json(silent=True) or {}
    interview = director_interview_service.update_interview(interview_id, payload)
    if not interview:
        return jsonify({"message": "约谈记录不存在"}), 404
    return jsonify(interview)


@director_interview_bp.delete("/<interview_id>")
def delete_interview(interview_id: str):
    deleted = director_interview_service.delete_interview(interview_id)
    if not deleted:
        return jsonify({"message": "约谈记录不存在"}), 404
    return jsonify({"ok": True})


@director_interview_bp.post("/<interview_id>/images")
def upload_images(interview_id: str):
    payload = request.get_json(silent=True) or {}
    files = payload.get("files", [])
    if not files:
        return jsonify({"message": "没有上传文件"}), 400
    try:
        images = director_interview_service.save_interview_images(interview_id, files)
    except ValueError as exc:
        return jsonify({"message": str(exc)}), 400
    return jsonify({"images": images}), 201


@director_interview_bp.delete("/<interview_id>/images/<image_id>")
def delete_image(interview_id: str, image_id: str):
    deleted = director_interview_service.delete_interview_image(interview_id, image_id)
    if not deleted:
        return jsonify({"message": "图片不存在"}), 404
    return jsonify({"ok": True})


@director_interview_bp.get("/<interview_id>/export")
def export_interview(interview_id: str):
    try:
        docx_bytes = director_interview_service.export_interview_docx(interview_id)
    except ImportError as exc:
        return jsonify({"message": str(exc)}), 500
    except Exception as exc:
        import traceback
        traceback.print_exc()
        return jsonify({"message": f"导出失败: {exc}"}), 500

    if docx_bytes is None:
        return jsonify({"message": "约谈记录不存在"}), 404

    interview = director_interview_service.get_interview(interview_id)
    name = interview.get("employeeName", "unknown") if interview else "unknown"
    date_str = interview.get("interviewDate", "") if interview else ""
    date_clean = date_str.replace("-", ".")
    filename = f"【主任座谈会】-{name}-{date_clean}.docx"

    return Response(
        docx_bytes,
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}",
        },
    )
