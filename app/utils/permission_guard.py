from __future__ import annotations

from functools import wraps

from flask import jsonify
from flask_jwt_extended import get_jwt, jwt_required

from app.services.permission_service import personnel_has_permission


def require_permission(permission_code: str):
    """要求已登录且拥有指定权限码。"""

    def decorator(fn):
        @wraps(fn)
        @jwt_required()
        def wrapper(*args, **kwargs):
            claims = get_jwt()
            personnel_id = (claims.get("personnel_id") or "").strip()
            if not personnel_id:
                return jsonify({"message": "请先登录"}), 401
            if not personnel_has_permission(personnel_id, permission_code):
                return jsonify({"message": "无权访问该资源"}), 403
            return fn(*args, **kwargs)

        return wrapper

    return decorator
