from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from app.services import auth_service

auth_bp = Blueprint("auth", __name__)


@auth_bp.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    result, error, status = auth_service.login(username, password)
    if error:
        return jsonify({"message": error}), status
    return jsonify(result), status


@auth_bp.post("/change-password")
@jwt_required()
def change_password():
    data = request.get_json(silent=True) or {}
    result, error, status = auth_service.change_password(
        data.get("oldPassword") or "",
        data.get("newPassword") or "",
    )
    if error:
        return jsonify({"message": error}), status
    return jsonify(result), status


@auth_bp.get("/me")
@jwt_required()
def current_user():
    result, error, status = auth_service.get_current_user()
    if error:
        return jsonify({"message": error}), status
    return jsonify(result), status
