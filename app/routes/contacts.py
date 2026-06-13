from flask import Blueprint, jsonify, request

from app.services import contact_service
from app.utils.pagination import parse_list_page_query

contacts_bp = Blueprint("contacts", __name__)


@contacts_bp.get("")
def list_contacts():
    page_query = parse_list_page_query(request.args)
    result = contact_service.list_contacts(
        keyword=request.args.get("keyword", ""),
        status=request.args.get("status", ""),
        page_query=page_query,
    )
    return jsonify(result)


@contacts_bp.get("/<contact_id>")
def get_contact(contact_id: str):
    contact = contact_service.get_contact_by_id(contact_id)
    if not contact:
        return jsonify({"message": "联系单不存在"}), 404
    return jsonify(contact)


@contacts_bp.post("")
def create_contact():
    payload = request.get_json(silent=True) or {}
    title = str(payload.get("title", "")).strip()
    received_date = str(payload.get("receivedDate", "")).strip()
    if not title or not received_date:
        return jsonify({"message": "联系主题和收单日期不能为空"}), 400
    contact = contact_service.create_contact(payload)
    return jsonify(contact), 201


@contacts_bp.put("/<contact_id>")
def update_contact(contact_id: str):
    payload = request.get_json(silent=True) or {}
    contact = contact_service.update_contact(contact_id, payload)
    if not contact:
        return jsonify({"message": "联系单不存在"}), 404
    return jsonify(contact)


@contacts_bp.delete("/<contact_id>")
def delete_contact(contact_id: str):
    deleted = contact_service.delete_contact(contact_id)
    if not deleted:
        return jsonify({"message": "联系单不存在"}), 404
    return jsonify({"ok": True})


@contacts_bp.post("/<contact_id>/attachments")
def append_attachments(contact_id: str):
    payload = request.get_json(silent=True) or {}
    files = payload.get("files") or []
    if not files:
        return jsonify({"message": "请提供 PDF 附件"}), 400
    contact = contact_service.append_supplement_attachments(contact_id, files)
    if not contact:
        return jsonify({"message": "联系单不存在"}), 404
    return jsonify(contact)


@contacts_bp.post("/<parent_id>/children")
def create_child_contact(parent_id: str):
    payload = request.get_json(silent=True) or {}
    title = str(payload.get("title", "")).strip()
    received_date = str(payload.get("receivedDate", "")).strip()
    if not title or not received_date:
        return jsonify({"message": "联系主题和收单日期不能为空"}), 400
    contact = contact_service.create_child_contact(parent_id, payload)
    if not contact:
        return jsonify({"message": "父联系单不存在"}), 404
    return jsonify(contact), 201
