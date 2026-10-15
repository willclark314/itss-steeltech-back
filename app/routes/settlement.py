"""钢结构技术科结算 API 路由"""

from __future__ import annotations

from urllib.parse import quote

from flask import Blueprint, Response, jsonify, request
from flask_jwt_extended import jwt_required

from app.services import settlement_service
from app.services.auth_scope import is_jwt_admin
from app.utils.route_permissions import register_any_permission_guard

settlement_bp = Blueprint("settlement", __name__)

register_any_permission_guard(settlement_bp, "settlement-record:view")


@settlement_bp.get("/pending")
def list_pending_items():
    category = request.args.get("category")
    return jsonify(settlement_service.list_pending_items(category=category))


@settlement_bp.post("/pending/batch")
@jwt_required()
def batch_save_pending_items():
    data = request.get_json(silent=True) or []
    if not isinstance(data, list):
        return jsonify({"message": "请求体必须是数组"}), 400

    result, error, status = settlement_service.batch_replace_pending_items(data)
    if error:
        return jsonify({"message": error}), status
    return jsonify(result), status


@settlement_bp.post("/pending/attach-to-month")
@jwt_required()
def attach_pending_to_month():
    data = request.get_json(silent=True) or {}
    category = data.get("category")
    year = data.get("year")
    month = data.get("month")
    pending_ids = data.get("pendingIds") or None
    if pending_ids == []:
        pending_ids = None

    if not category or year is None or month is None:
        return jsonify({"message": "请提供 category、year 和 month 参数"}), 400

    try:
        year_i = int(year)
        month_i = int(month)
    except (TypeError, ValueError):
        return jsonify({"message": "year 和 month 必须为整数"}), 400

    if pending_ids is not None and not isinstance(pending_ids, list):
        return jsonify({"message": "pendingIds 必须是数组"}), 400

    result, error, status = settlement_service.attach_pending_items_to_month(
        year=year_i, month=month_i, category=category, pending_ids=pending_ids
    )
    if error:
        return jsonify({"message": error}), status
    return jsonify(result), status


@settlement_bp.post("/records/move-to-pending")
@jwt_required()
def move_month_records_to_pending():
    data = request.get_json(silent=True) or {}
    category = data.get("category")
    year = data.get("year")
    month = data.get("month")
    record_ids = data.get("recordIds") or None
    if record_ids == []:
        record_ids = None

    if not category or year is None or month is None:
        return jsonify({"message": "请提供 category、year 和 month 参数"}), 400

    try:
        year_i = int(year)
        month_i = int(month)
    except (TypeError, ValueError):
        return jsonify({"message": "year 和 month 必须为整数"}), 400

    if record_ids is not None and not isinstance(record_ids, list):
        return jsonify({"message": "recordIds 必须是数组"}), 400

    result, error, status = settlement_service.move_month_records_to_pending(
        year=year_i, month=month_i, category=category, record_ids=record_ids
    )
    if error:
        return jsonify({"message": error}), status
    return jsonify(result), status


@settlement_bp.get("/records")
def list_settlement_records():
    year_str = request.args.get("year")
    month_str = request.args.get("month")
    category = request.args.get("category")
    year = int(year_str) if year_str else None
    month = int(month_str) if month_str else None
    return jsonify(
        settlement_service.list_settlement_records(year=year, month=month, category=category)
    )


@settlement_bp.post("/records/batch")
@jwt_required()
def batch_save_settlement_records():
    data = request.get_json(silent=True) or []
    if not isinstance(data, list):
        return jsonify({"message": "请求体必须是数组"}), 400

    result, error, status = settlement_service.batch_replace_month_records(data)
    if error:
        return jsonify({"message": error}), status
    return jsonify(result), status


@settlement_bp.get("/records/export")
@jwt_required()
def export_settlement_records():
    year_str = request.args.get("year")
    month_str = request.args.get("month")
    category = request.args.get("category")
    if not year_str or not month_str or not category:
        return jsonify({"message": "请提供 year、month 和 category 参数"}), 400

    try:
        year = int(year_str)
        month = int(month_str)
    except ValueError:
        return jsonify({"message": "year 和 month 必须为整数"}), 400

    if month < 1 or month > 12:
        return jsonify({"message": "月份必须在 1-12 之间"}), 400

    try:
        excel_bytes = settlement_service.export_settlement_records_excel(year, month, category)
    except Exception as exc:
        return jsonify({"message": f"生成 Excel 失败: {exc}"}), 500

    label = "细化" if category == "detail" else "设计"
    filename = f"钢结构技术科{year}年{month}月{label}结算.xlsx"
    return Response(
        excel_bytes,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename, safe='')}",
        },
    )


@settlement_bp.post("/records/import")
@jwt_required()
def import_settlement_records():
    if not is_jwt_admin():
        return jsonify({"message": "无权限，仅管理员可导入"}), 403

    upload = request.files.get("file")
    if upload is None:
        return jsonify({"message": "请上传 Excel 文件"}), 400

    year_str = request.form.get("year")
    month_str = request.form.get("month")
    category = request.form.get("category")
    year = int(year_str) if year_str else None
    month = int(month_str) if month_str else None

    try:
        file_bytes = upload.read()
    except Exception as exc:
        return jsonify({"message": f"读取文件失败: {exc}"}), 400

    result, error, status = settlement_service.import_settlement_records_excel(
        file_bytes,
        year=year,
        month=month,
        category=category,
    )
    if error:
        return jsonify({"message": error}), status
    return jsonify(result), status


@settlement_bp.get("/pricing")
def list_pricing_basis():
    category = request.args.get("category")
    return jsonify(settlement_service.list_pricing_basis(category=category))


@settlement_bp.get("/pricing/lookup")
def lookup_pricing():
    category = request.args.get("category")
    pricing_code = request.args.get("pricingCode")
    if not category or not pricing_code:
        return jsonify({"message": "请提供 category 和 pricingCode 参数"}), 400
    result = settlement_service.get_pricing_by_code(category=category, pricing_code=pricing_code)
    if not result:
        return jsonify({"message": "未找到对应定价条目"}), 404
    return jsonify(result)


@settlement_bp.post("/pricing/import")
@jwt_required()
def import_pricing_basis():
    if not is_jwt_admin():
        return jsonify({"message": "无权限，仅管理员可导入"}), 403

    upload = request.files.get("file")
    if upload is None:
        return jsonify({"message": "请上传 Excel 文件"}), 400

    try:
        file_bytes = upload.read()
    except Exception as exc:
        return jsonify({"message": f"读取文件失败: {exc}"}), 400

    result, error, status = settlement_service.import_pricing_basis_excel(file_bytes)
    if error:
        return jsonify({"message": error}), status
    return jsonify(result), status
