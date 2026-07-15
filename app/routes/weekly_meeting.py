from urllib.parse import quote

from flask import Blueprint, Response, jsonify, request

from app.services import weekly_meeting_service

weekly_meeting_bp = Blueprint("weekly_meeting", __name__)


@weekly_meeting_bp.get("")
def list_meetings():
    year = request.args.get("year", "")
    month = request.args.get("month", "")
    result = weekly_meeting_service.list_meetings(year=year, month=month)
    return jsonify(result)


@weekly_meeting_bp.get("/<meeting_id>")
def get_meeting(meeting_id: str):
    meeting = weekly_meeting_service.get_meeting(meeting_id)
    if not meeting:
        return jsonify({"message": "会议记录不存在"}), 404
    return jsonify(meeting)


@weekly_meeting_bp.post("")
def create_meeting():
    payload = request.get_json(silent=True) or {}
    meeting_date = str(payload.get("meetingDate", "")).strip()
    meeting_theme = str(payload.get("meetingTheme", "")).strip()
    if not meeting_date or not meeting_theme:
        return jsonify({"message": "会议日期和主题不能为空"}), 400
    meeting = weekly_meeting_service.create_meeting(payload)
    return jsonify(meeting), 201


@weekly_meeting_bp.put("/<meeting_id>")
def update_meeting(meeting_id: str):
    payload = request.get_json(silent=True) or {}
    meeting = weekly_meeting_service.update_meeting(meeting_id, payload)
    if not meeting:
        return jsonify({"message": "会议记录不存在"}), 404
    return jsonify(meeting)


@weekly_meeting_bp.delete("/<meeting_id>")
def delete_meeting(meeting_id: str):
    deleted = weekly_meeting_service.delete_meeting(meeting_id)
    if not deleted:
        return jsonify({"message": "会议记录不存在"}), 404
    return jsonify({"ok": True})


@weekly_meeting_bp.post("/<meeting_id>/images")
def upload_images(meeting_id: str):
    payload = request.get_json(silent=True) or {}
    files = payload.get("files", [])
    if not files:
        return jsonify({"message": "没有上传文件"}), 400
    try:
        images = weekly_meeting_service.save_meeting_images(meeting_id, files)
    except ValueError as exc:
        return jsonify({"message": str(exc)}), 400
    return jsonify({"images": images}), 201


@weekly_meeting_bp.delete("/<meeting_id>/images/<image_id>")
def delete_image(meeting_id: str, image_id: str):
    deleted = weekly_meeting_service.delete_meeting_image(meeting_id, image_id)
    if not deleted:
        return jsonify({"message": "图片不存在"}), 404
    return jsonify({"ok": True})


@weekly_meeting_bp.post("/<meeting_id>/scan")
def upload_scan(meeting_id: str):
    payload = request.get_json(silent=True) or {}
    file_info = payload.get("file")
    if not file_info:
        return jsonify({"message": "没有上传文件"}), 400
    try:
        scan = weekly_meeting_service.save_meeting_scan(meeting_id, file_info)
    except ValueError as exc:
        return jsonify({"message": str(exc)}), 400
    return jsonify({"recordScan": scan}), 201


@weekly_meeting_bp.delete("/<meeting_id>/scan")
def delete_scan(meeting_id: str):
    deleted = weekly_meeting_service.delete_meeting_scan(meeting_id)
    if not deleted:
        return jsonify({"message": "扫描件不存在"}), 404
    return jsonify({"ok": True})


@weekly_meeting_bp.get("/<meeting_id>/export")
def export_meeting(meeting_id: str):
    try:
        docx_bytes = weekly_meeting_service.export_meeting_docx(meeting_id)
    except ImportError as exc:
        return jsonify({"message": str(exc)}), 500
    except Exception as exc:
        import traceback
        traceback.print_exc()
        return jsonify({"message": f"导出失败: {exc}"}), 500

    if docx_bytes is None:
        return jsonify({"message": "会议记录不存在"}), 404

    meeting = weekly_meeting_service.get_meeting(meeting_id)
    meeting_date = meeting["meetingDate"] if meeting else "unknown"
    filename = f"【例会纪要与签到表】{meeting_date}.docx"

    return Response(
        docx_bytes,
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}",
        },
    )
