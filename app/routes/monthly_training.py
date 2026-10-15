from urllib.parse import quote

from flask import Blueprint, Response, jsonify, request

from app.services import monthly_training_service

monthly_training_bp = Blueprint("monthly_training", __name__)


@monthly_training_bp.get("")
def list_trainings():
    year = request.args.get("year", "")
    month = request.args.get("month", "")
    result = monthly_training_service.list_trainings(year=year, month=month)
    return jsonify(result)


@monthly_training_bp.get("/<training_id>")
def get_training(training_id: str):
    training = monthly_training_service.get_training(training_id)
    if not training:
        return jsonify({"message": "培训记录不存在"}), 404
    return jsonify(training)


@monthly_training_bp.post("")
def create_training():
    payload = request.get_json(silent=True) or {}
    year = str(payload.get("trainingYear", "")).strip()
    month = str(payload.get("trainingMonth", "")).strip()
    title = str(payload.get("title", "")).strip()
    if not year or not month or not title:
        return jsonify({"message": "年度、月份和培训主题不能为空"}), 400
    training = monthly_training_service.create_training(payload)
    return jsonify(training), 201


@monthly_training_bp.put("/<training_id>")
def update_training(training_id: str):
    payload = request.get_json(silent=True) or {}
    training = monthly_training_service.update_training(training_id, payload)
    if not training:
        return jsonify({"message": "培训记录不存在"}), 404
    return jsonify(training)


@monthly_training_bp.delete("/<training_id>")
def delete_training(training_id: str):
    deleted = monthly_training_service.delete_training(training_id)
    if not deleted:
        return jsonify({"message": "培训记录不存在"}), 404
    return jsonify({"ok": True})


@monthly_training_bp.post("/<training_id>/primary-pdf")
def upload_primary_pdf(training_id: str):
    payload = request.get_json(silent=True) or {}
    file_info = payload.get("file")
    if not file_info:
        return jsonify({"message": "没有上传文件"}), 400
    try:
        training = monthly_training_service.save_training_primary_pdf(
            training_id, file_info
        )
    except ValueError as exc:
        return jsonify({"message": str(exc)}), 400
    return jsonify(training)


@monthly_training_bp.delete("/<training_id>/primary-pdf")
def delete_primary_pdf(training_id: str):
    deleted = monthly_training_service.delete_training_primary_pdf(training_id)
    if not deleted:
        return jsonify({"message": "培训记录不存在"}), 404
    return jsonify({"ok": True})


@monthly_training_bp.post("/<training_id>/materials")
def upload_material(training_id: str):
    payload = request.get_json(silent=True) or {}
    file_info = payload.get("file")
    material_type = str(payload.get("materialType", "")).strip()
    if not file_info:
        return jsonify({"message": "没有上传文件"}), 400
    try:
        material = monthly_training_service.save_training_material(
            training_id, file_info, material_type
        )
    except ValueError as exc:
        return jsonify({"message": str(exc)}), 400
    return jsonify({"material": material}), 201


@monthly_training_bp.delete("/<training_id>/materials/<material_id>")
def delete_material(training_id: str, material_id: str):
    deleted = monthly_training_service.delete_training_material(
        training_id, material_id
    )
    if not deleted:
        return jsonify({"message": "文件不存在"}), 404
    return jsonify({"ok": True})


@monthly_training_bp.post("/<training_id>/photos")
def upload_photos(training_id: str):
    payload = request.get_json(silent=True) or {}
    files = payload.get("files", [])
    if not files:
        return jsonify({"message": "没有上传文件"}), 400
    try:
        photos = monthly_training_service.save_training_photos(training_id, files)
    except ValueError as exc:
        return jsonify({"message": str(exc)}), 400
    return jsonify({"photos": photos}), 201


@monthly_training_bp.delete("/<training_id>/photos/<photo_id>")
def delete_photo(training_id: str, photo_id: str):
    deleted = monthly_training_service.delete_training_photo(training_id, photo_id)
    if not deleted:
        return jsonify({"message": "照片不存在"}), 404
    return jsonify({"ok": True})


@monthly_training_bp.get("/<training_id>/export")
def export_training(training_id: str):
    try:
        docx_bytes = monthly_training_service.export_training_docx(training_id)
    except ImportError as exc:
        return jsonify({"message": str(exc)}), 500
    except Exception as exc:
        import traceback
        traceback.print_exc()
        return jsonify({"message": f"导出失败: {exc}"}), 500

    if docx_bytes is None:
        return jsonify({"message": "培训记录不存在"}), 404

    training = monthly_training_service.get_training(training_id)
    title = training["title"] if training else "unknown"
    ym = (
        f"{training['trainingYear']}{training['trainingMonth']}"
        if training
        else "unknown"
    )
    filename = f"【签到表及照片页】{ym}-{title}.docx"

    return Response(
        docx_bytes,
        mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}",
        },
    )
