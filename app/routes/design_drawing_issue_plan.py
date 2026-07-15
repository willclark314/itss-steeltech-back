"""钢构设计发图计划 API 路由"""

from __future__ import annotations

from urllib.parse import quote

from flask import Blueprint, Response, jsonify, request
from flask_jwt_extended import jwt_required

from app.services import design_drawing_issue_plan_service
from app.services.auth_scope import is_jwt_admin
from app.utils.route_permissions import register_any_permission_guard

design_drawing_issue_plan_bp = Blueprint("design_drawing_issue_plan", __name__)

register_any_permission_guard(design_drawing_issue_plan_bp, "design-drawing-issue-plan:view")


@design_drawing_issue_plan_bp.get("")
def list_design_drawing_issue_plans():
    year_str = request.args.get("year")
    month_str = request.args.get("month")
    year = int(year_str) if year_str else None
    month = int(month_str) if month_str else None
    return jsonify(design_drawing_issue_plan_service.list_design_drawing_issue_plans(year=year, month=month))


@design_drawing_issue_plan_bp.post("/batch")
@jwt_required()
def batch_save_design_drawing_issue_plans():
    data = request.get_json(silent=True) or []
    if not isinstance(data, list):
        return jsonify({"message": "请求体必须是数组"}), 400

    result, error, status = design_drawing_issue_plan_service.batch_replace_month_plans(data)
    if error:
        return jsonify({"message": error}), status
    return jsonify(result), status


@design_drawing_issue_plan_bp.get("/export")
@jwt_required()
def export_design_drawing_issue_plan():
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
        excel_bytes = design_drawing_issue_plan_service.export_design_drawing_issue_plan_excel(year, month)
    except Exception as exc:
        return jsonify({"message": f"生成 Excel 失败: {exc}"}), 500

    filename = f"设备技术部{year}年{month}月钢构设计发图计划.xlsx"
    return Response(
        excel_bytes,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename, safe='')}",
        },
    )


@design_drawing_issue_plan_bp.post("/import")
@jwt_required()
def import_design_drawing_issue_plan():
    if not is_jwt_admin():
        return jsonify({"message": "无权限，仅管理员可导入"}), 403

    upload = request.files.get("file")
    if upload is None:
        return jsonify({"message": "请上传 Excel 文件"}), 400

    year_str = request.form.get("year")
    month_str = request.form.get("month")
    year = int(year_str) if year_str else None
    month = int(month_str) if month_str else None

    try:
        file_bytes = upload.read()
    except Exception as exc:
        return jsonify({"message": f"读取文件失败: {exc}"}), 400

    result, error, status = design_drawing_issue_plan_service.import_design_drawing_issue_plan_excel(
        file_bytes,
        year=year,
        month=month,
    )
    if error:
        return jsonify({"message": error}), status
    return jsonify(result), status


@design_drawing_issue_plan_bp.get("/settings")
def get_design_drawing_issue_plan_settings():
    return jsonify(design_drawing_issue_plan_service.get_display_settings())


@design_drawing_issue_plan_bp.put("/settings")
@jwt_required()
def save_design_drawing_issue_plan_settings():
    data = request.get_json(silent=True) or {}
    try:
        settings = design_drawing_issue_plan_service.save_display_settings(data)
    except ValueError as exc:
        return jsonify({"message": str(exc)}), 400
    return jsonify(settings)
