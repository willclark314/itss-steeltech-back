"""月休计划 API 路由"""

from __future__ import annotations

from typing import Optional

from flask import Blueprint, Response, jsonify, request
from flask_jwt_extended import get_jwt, jwt_required

from steeltech_db.extensions import db
from steeltech_db.models import Role, RolePersonnel
from app.services import monthly_rest_service

monthly_rest_bp = Blueprint("monthly_rest", __name__)


def _get_personnel_id_from_token() -> Optional[str]:
    """从 JWT 中提取当前用户的 personnel_id"""
    try:
        claims = get_jwt()
        return claims.get("personnel_id")
    except RuntimeError:
        return None


@monthly_rest_bp.get("")
def list_monthly_rest():
    year_str = request.args.get("year")
    month_str = request.args.get("month")
    year = int(year_str) if year_str else None
    month = int(month_str) if month_str else None
    return jsonify(monthly_rest_service.list_monthly_rest(year=year, month=month))


@monthly_rest_bp.get("/status")
@jwt_required()
def monthly_rest_status():
    """返回指定年月是否已定稿锁定"""
    year_str = request.args.get("year")
    month_str = request.args.get("month")
    if not year_str or not month_str:
        return jsonify({"message": "请提供 year 和 month 参数"}), 400
    try:
        year = int(year_str)
        month = int(month_str)
    except ValueError:
        return jsonify({"message": "year 和 month 必须为整数"}), 400
    return jsonify(monthly_rest_service.get_month_lock(year=year, month=month))


@monthly_rest_bp.get("/my-scope")
@jwt_required()
def my_scope():
    """返回当前用户的编辑范围"""
    personnel_id = _get_personnel_id_from_token()
    if not personnel_id:
        return jsonify({"message": "无法识别当前用户"}), 401
    scope = monthly_rest_service.get_user_scope(personnel_id)
    return jsonify(scope)


@monthly_rest_bp.post("")
@jwt_required()
def save_monthly_rest():
    data = request.get_json(silent=True) or {}
    result, error, status = monthly_rest_service.save_monthly_rest(data)
    if error:
        return jsonify({"message": error}), status
    return jsonify(result), status


@monthly_rest_bp.post("/batch")
@jwt_required()
def batch_save_monthly_rest():
    data = request.get_json(silent=True) or []
    if not isinstance(data, list):
        return jsonify({"message": "请求体必须是数组"}), 400

    editor_personnel_id = _get_personnel_id_from_token()
    result, error, status = monthly_rest_service.batch_save_monthly_rest(
        data, editor_personnel_id=editor_personnel_id
    )
    if error:
        return jsonify({"message": error}), status
    return jsonify(result), status


@monthly_rest_bp.post("/finalize")
@jwt_required()
def finalize_monthly_rest():
    """管理员保存并定稿锁定该月（员工不可再改）"""
    if not _check_is_admin():
        return jsonify({"message": "无权限，仅管理员可定稿"}), 403

    data = request.get_json(silent=True) or []
    if not isinstance(data, list):
        return jsonify({"message": "请求体必须是数组"}), 400

    editor_personnel_id = _get_personnel_id_from_token()
    if not editor_personnel_id:
        return jsonify({"message": "无法识别当前用户"}), 401

    result, error, status = monthly_rest_service.finalize_monthly_rest(
        data, editor_personnel_id=editor_personnel_id
    )
    if error:
        return jsonify({"message": error}), status
    return jsonify(result), status


@monthly_rest_bp.delete("/<record_id>")
@jwt_required()
def delete_monthly_rest(record_id: str):
    result, error, status = monthly_rest_service.delete_monthly_rest(record_id)
    if error:
        return jsonify({"message": error}), status
    return jsonify(result), status


def _check_is_admin() -> bool:
    """检查当前 JWT 用户是否为管理员（dev 账号或拥有 admin 角色）"""
    try:
        claims = get_jwt()
    except RuntimeError:
        return False

    # dev 账号直接通过
    if claims.get("login_type") == "dev":
        return True

    # 检查是否拥有 admin 角色
    personnel_id = claims.get("personnel_id")
    if not personnel_id:
        return False

    admin_role = (
        db.session.query(RolePersonnel)
        .join(Role, Role.id == RolePersonnel.role_id)
        .filter(RolePersonnel.personnel_id == personnel_id, Role.code == "admin")
        .first()
    )
    return admin_role is not None


@monthly_rest_bp.get("/export")
@jwt_required()
def export_monthly_rest():
    """导出月休计划为 Excel 文件（仅管理员可用）"""
    if not _check_is_admin():
        return jsonify({"message": "无权限，仅管理员可导出"}), 403

    year_str = request.args.get("year")
    month_str = request.args.get("month")
    if not year_str or not month_str:
        return jsonify({"message": "请提供 year 和 month 参数"}), 400

    try:
        year = int(year_str)
        month = int(month_str)
    except ValueError:
        return jsonify({"message": "year 和 month 必须为整数"}), 400

    if month < 1 or month > 12:
        return jsonify({"message": "月份必须在 1-12 之间"}), 400

    try:
        excel_bytes = monthly_rest_service.export_monthly_rest_excel(year, month)
    except Exception as e:
        return jsonify({"message": f"生成 Excel 失败: {str(e)}"}), 500

    filename = f"{year}年{month}月调休汇总表（钢结构技术科）.xlsx"
    return Response(
        excel_bytes,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{_url_quote(filename)}",
        },
    )


def _url_quote(s: str) -> str:
    """简单的 URL 编码（仅处理中文字符所需的编码）"""
    from urllib.parse import quote
    return quote(s, safe="")
