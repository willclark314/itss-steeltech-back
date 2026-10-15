from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_jwt_extended import get_jwt, verify_jwt_in_request

from app.services.permission_service import personnel_has_any_permission


def _resolve_personnel_id() -> tuple[str | None, tuple | None]:
    try:
        verify_jwt_in_request()
    except Exception:
        return None, (jsonify({"message": "请先登录"}), 401)
    claims = get_jwt()
    personnel_id = (claims.get("personnel_id") or "").strip()
    if not personnel_id:
        return None, (jsonify({"message": "请先登录"}), 401)
    return personnel_id, None


def register_any_permission_guard(blueprint: Blueprint, *permission_codes: str) -> None:
    codes = [code.strip() for code in permission_codes if (code or "").strip()]
    if not codes:
        return

    @blueprint.before_request
    def _guard():
        if request.method == "OPTIONS":
            return None
        personnel_id, error_response = _resolve_personnel_id()
        if error_response:
            return error_response
        if personnel_id and not personnel_has_any_permission(personnel_id, codes):
            return jsonify({"message": "无权访问该资源"}), 403
        return None


def register_read_write_guard(
    blueprint: Blueprint,
    *,
    view_codes: tuple[str, ...],
    read_codes: tuple[str, ...] | None = None,
    my_write_codes: tuple[str, ...] = (),
    restricted_get_suffixes: tuple[str, ...] = (),
) -> None:
    """读写权限守卫。

    - 写操作（非 GET/HEAD）默认要求 view_codes
    - 读操作默认可用 read_codes（未传则同 view_codes）
    - restricted_get_suffixes 命中的读路径仍只用 view_codes（如导出）
    """

    @blueprint.before_request
    def _guard():
        if request.method == "OPTIONS":
            return None
        personnel_id, error_response = _resolve_personnel_id()
        if error_response:
            return error_response
        if not personnel_id:
            return None

        path = request.path or ""
        if request.method in ("GET", "HEAD"):
            if any(path.rstrip("/").endswith(suffix.rstrip("/")) for suffix in restricted_get_suffixes):
                allowed_codes = list(view_codes)
            else:
                allowed_codes = list(read_codes or view_codes)
        else:
            allowed_codes = list(view_codes)
            if my_write_codes and ("/detail-workflow" in path or "/design-workflow" in path):
                allowed_codes.extend(my_write_codes)

        if not personnel_has_any_permission(personnel_id, allowed_codes):
            return jsonify({"message": "无权访问该资源"}), 403
        return None
