from flask import Blueprint, jsonify, request

from app.services import change_order_service
from app.utils.pagination import parse_list_page_query
from app.utils.route_permissions import register_read_write_guard

change_orders_bp = Blueprint("change_orders", __name__)

register_read_write_guard(
    change_orders_bp,
    view_codes=("change-order:view", "change-order-browse:view"),
)


@change_orders_bp.get("")
def list_change_orders():
    page_query = parse_list_page_query(request.args)
    result = change_order_service.list_change_orders(
        keyword=request.args.get("keyword", ""),
        page_query=page_query,
    )
    return jsonify(result)


@change_orders_bp.post("/pdfs/check")
def check_change_order_pdf():
    payload = request.get_json(silent=True) or {}
    file_md5 = str(payload.get("md5", "")).strip().lower()
    if len(file_md5) != 32:
        return jsonify({"message": "无效的 MD5"}), 400
    return jsonify(change_order_service.check_pdf_md5(file_md5))


@change_orders_bp.get("/<change_order_id>")
def get_change_order(change_order_id):
    order = change_order_service.get_change_order_by_id(change_order_id)
    if not order:
        return jsonify({"message": "变更单不存在"}), 404
    return jsonify(order)


@change_orders_bp.post("")
def create_change_order():
    payload = request.get_json(silent=True) or {}
    title = str(payload.get("title", "")).strip()
    if not title:
        return jsonify({"message": "变更主题不能为空"}), 400
    try:
        order = change_order_service.create_change_order(payload)
    except ValueError as exc:
        return jsonify({"message": str(exc)}), 400
    return jsonify(order), 201


@change_orders_bp.put("/<change_order_id>")
def update_change_order(change_order_id):
    payload = request.get_json(silent=True) or {}
    try:
        order = change_order_service.update_change_order(change_order_id, payload)
    except ValueError as exc:
        return jsonify({"message": str(exc)}), 400
    if not order:
        return jsonify({"message": "变更单不存在"}), 404
    return jsonify(order)


@change_orders_bp.post("/<change_order_id>/primary-files")
@change_orders_bp.post("/<change_order_id>/attachments")
def append_primary_files(change_order_id):
    """追加正文文件。保留 /attachments 路径以兼容旧客户端。"""
    payload = request.get_json(silent=True) or {}
    files = payload.get("files") or []
    if not files:
        return jsonify({"message": "请提供正文文件"}), 400
    try:
        order = change_order_service.append_primary_files(change_order_id, files)
    except ValueError as exc:
        return jsonify({"message": str(exc)}), 400
    if not order:
        return jsonify({"message": "变更单不存在"}), 404
    return jsonify(order)


@change_orders_bp.delete("/<change_order_id>")
def delete_change_order(change_order_id):
    deleted = change_order_service.delete_change_order(change_order_id)
    if not deleted:
        return jsonify({"message": "变更单不存在"}), 404
    return jsonify({"ok": True})
