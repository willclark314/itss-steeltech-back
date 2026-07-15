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
) -> None:
    @blueprint.before_request
    def _guard():
        if request.method == "OPTIONS":
            return None
        personnel_id, error_response = _resolve_personnel_id()
        if error_response:
            return error_response
        if not personnel_id:
            return None

        if request.method in ("GET", "HEAD"):
            allowed_codes = list(read_codes or view_codes)
        else:
            allowed_codes = list(view_codes)
            path = request.path or ""
            if my_write_codes and ("/detail-workflow" in path or "/design-workflow" in path):
                allowed_codes.extend(my_write_codes)

        if not personnel_has_any_permission(personnel_id, allowed_codes):
            return jsonify({"message": "无权访问该资源"}), 403
        return None
