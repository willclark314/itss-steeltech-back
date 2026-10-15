"""数据库双向迁移 API —— 管理员（系统设置权限）。"""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from app.services.db_migrate_service import DbMigrateService
from app.utils.route_permissions import register_read_write_guard

db_migrate_bp = Blueprint("db_migrate", __name__)
service = DbMigrateService()

register_read_write_guard(
    db_migrate_bp,
    view_codes=("system-settings:view",),
)


@db_migrate_bp.get("/status")
def migrate_status():
    return jsonify(service.get_status(current_app))


@db_migrate_bp.post("/preview")
def migrate_preview():
    data = request.get_json(silent=True) or {}
    target_url = (data.get("target_url") or "").strip()
    try:
        result = service.preview(current_app, target_url)
        return jsonify(result)
    except Exception as exc:
        return jsonify({"message": str(exc)}), 400


@db_migrate_bp.post("/run")
def migrate_run():
    data = request.get_json(silent=True) or {}
    target_url = (data.get("target_url") or "").strip()
    mode = (data.get("mode") or "upsert").strip().lower()
    if mode not in ("upsert", "replace"):
        return jsonify({"message": "mode 仅支持 upsert / replace"}), 400
    backup_first = data.get("backup_first", True)
    if not isinstance(backup_first, bool):
        backup_first = str(backup_first).strip().lower() in ("1", "true", "yes", "on")

    try:
        result = service.run(
            current_app,
            target_url=target_url,
            mode=mode,  # type: ignore[arg-type]
            backup_first=backup_first,
        )
        return jsonify(result)
    except Exception as exc:
        return jsonify({"message": str(exc)}), 400


@db_migrate_bp.post("/verify")
def migrate_verify():
    data = request.get_json(silent=True) or {}
    target_url = (data.get("target_url") or "").strip()
    try:
        result = service.verify(current_app, target_url)
        return jsonify(result)
    except Exception as exc:
        return jsonify({"message": str(exc)}), 400
