from flask import Blueprint, jsonify, request
from flask_jwt_extended import jwt_required

from app.services import detail_team_schedule_service

detail_team_schedule_bp = Blueprint("detail_team_schedule", __name__)


@detail_team_schedule_bp.get("/member-order")
@jwt_required()
def get_member_order():
    result, error, status = detail_team_schedule_service.get_member_order()
    if error:
        return jsonify({"message": error}), status
    return jsonify(result), status


@detail_team_schedule_bp.put("/member-order")
@jwt_required()
def save_member_order():
    data = request.get_json(silent=True) or {}
    result, error, status = detail_team_schedule_service.save_member_order(data)
    if error:
        return jsonify({"message": error}), status
    return jsonify(result), status
