"""数据库备份 API 端点 —— 管理员专用"""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request, send_file

from app.services.backup_service import BackupService

backup_bp = Blueprint("backup", __name__)
service = BackupService()


@backup_bp.route("/config", methods=["GET", "PUT"])
def backup_config():
    if request.method == "PUT":
        data = request.get_json(silent=True) or {}
        try:
            config = service.apply_config(current_app, data)
            return jsonify({"message": "备份配置已更新", "config": config.to_dict()})
        except Exception as exc:
            return jsonify({"message": str(exc)}), 400

    return jsonify({"config": service.get_config_dict()})


@backup_bp.post("/trigger")
def trigger_backup():
    try:
        record = service.backup_now(current_app, trigger_type="manual")
        return jsonify({"message": "备份完成", "record": record.to_dict()})
    except Exception as exc:
        return jsonify({"message": f"备份失败: {exc}"}), 500


@backup_bp.get("/history")
def backup_history():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 20, type=int)
    return jsonify(service.get_history(page, per_page))


@backup_bp.get("/download/<int:record_id>")
def download_backup(record_id: int):
    from steeltech_db.models import BackupRecord

    record = BackupRecord.query.get_or_404(record_id)
    config = service.get_config()
    from pathlib import Path

    file_path = Path(current_app.root_path).parent / config.backup_dir / record.filename
    if not file_path.exists():
        return jsonify({"message": "备份文件不存在"}), 404

    return send_file(file_path, as_attachment=True, download_name=record.filename)


@backup_bp.delete("/<int:record_id>")
def delete_backup(record_id: int):
    try:
        service.delete_backup(record_id, app=current_app)
        return jsonify({"message": "已删除"})
    except Exception as exc:
        return jsonify({"message": str(exc)}), 400
