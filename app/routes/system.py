from __future__ import annotations

import os

from flask import Blueprint, jsonify, request

from app.services import folder_template_service, system_config_service
from app.services.folder_template_service import FolderTemplateError
from app.utils.network_host import get_local_ipv4_addresses, list_host_drives
from app.utils.paths import build_full_path, normalize_relative_path

system_bp = Blueprint("system", __name__)


def _normalize_full_path(path: str) -> str:
    trimmed = (path or "").strip()
    if not trimmed:
        return ""
    if trimmed.startswith("\\\\"):
        return trimmed.replace("/", "\\")
    return build_full_path(trimmed)


@system_bp.route("/config", methods=["GET", "PUT"])
def system_config():
    if request.method == "PUT":
        data = request.get_json(silent=True) or {}
        try:
            local_work_path = system_config_service.save_local_work_path_config(data)
            return jsonify({"localWorkPath": local_work_path})
        except ValueError as exc:
            return jsonify({"message": str(exc)}), 400

    return jsonify({"localWorkPath": system_config_service.get_local_work_path_config()})


@system_bp.get("/local-ip")
def local_ip():
    return jsonify({"ips": get_local_ipv4_addresses()})


@system_bp.get("/host-drives")
def host_drives():
    ip = (request.args.get("ip") or "").strip()
    try:
        return jsonify(list_host_drives(ip))
    except ValueError as exc:
        return jsonify({"message": str(exc)}), 400


@system_bp.get("/path-exists")
def path_exists():
    path = _normalize_full_path(request.args.get("path", ""))
    if not path:
        return jsonify({"message": "路径不能为空"}), 400
    try:
        exists = os.path.exists(path)
    except OSError:
        exists = False
    return jsonify({"path": path, "exists": exists})


@system_bp.get("/folder-templates")
def folder_templates():
    try:
        return jsonify({"templates": folder_template_service.list_folder_templates()})
    except FolderTemplateError as exc:
        return jsonify({"message": str(exc)}), 500


@system_bp.post("/generate-work-path")
def generate_work_path():
    data = request.get_json(silent=True) or {}
    try:
        return jsonify(folder_template_service.generate_folder_structure(data))
    except FolderTemplateError as exc:
        return jsonify({"message": str(exc)}), 400
    except OSError as exc:
        return jsonify({"message": str(exc) or "生成目录失败"}), 500

