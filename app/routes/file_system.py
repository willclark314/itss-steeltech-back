import os
import subprocess
import sys

from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

file_system_bp = Blueprint("file_system", __name__)


@file_system_bp.post("/open-folder")
@jwt_required()
def open_folder():
    """在 Windows 资源管理器中打开指定文件夹（支持本地路径与 UNC 网络路径）。"""
    data = request.get_json(silent=True) or {}
    folder_path = (data.get("path") or "").strip()

    if not folder_path:
        return jsonify({"message": "文件夹路径不能为空"}), 400

    if not os.path.exists(folder_path):
        return jsonify({"message": f"文件夹不存在: {folder_path}"}), 404

    if not os.path.isdir(folder_path):
        return jsonify({"message": f"路径不是文件夹: {folder_path}"}), 400

    try:
        if sys.platform == "win32":
            # Windows: 使用 explorer 打开，支持本地路径和 UNC 网络路径
            subprocess.Popen(["explorer", folder_path])
        elif sys.platform == "darwin":
            subprocess.Popen(["open", folder_path])
        else:
            subprocess.Popen(["xdg-open", folder_path])
    except Exception as e:
        return jsonify({"message": f"打开文件夹失败: {str(e)}"}), 500

    return jsonify({"success": True, "path": folder_path})
