from __future__ import annotations

from steeltech_db.extensions import db
from steeltech_db.models import Personnel

DEFAULT_WORKSHOP = "钢结构技术科"


def list_personnel(*, keyword: str = "", status: str = "") -> list[dict]:
    rows = Personnel.query.order_by(Personnel.team, Personnel.name).all()
    keyword = keyword.strip().lower()
    result: list[dict] = []

    for row in rows:
        item = row.to_dict()
        if status and item["status"] != status:
            continue
        if keyword:
            searchable = " ".join(
                [
                    item["id"],
                    item["name"],
                    item["employeeNo"],
                    item["nationality"],
                    item["team"],
                    item["position"],
                    item["domesticPhone"],
                ]
            ).lower()
            if keyword not in searchable:
                continue
        result.append(item)
    return result


def _validate_payload(payload: dict) -> str | None:
    if not (payload.get("name") or "").strip():
        return "姓名不能为空"
    if not (payload.get("employeeNo") or "").strip():
        return "工号不能为空"
    if not (payload.get("team") or "").strip():
        return "班组不能为空"
    if not (payload.get("nationality") or "").strip():
        return "国籍不能为空"
    if not (payload.get("status") or "").strip():
        return "状态不能为空"
    return None


def update_personnel(personnel_id: str, payload: dict) -> tuple[dict | None, str | None, int]:
    row = Personnel.query.get(personnel_id)
    if row is None:
        return None, "人员不存在", 404

    error = _validate_payload(payload)
    if error:
        return None, error, 400

    row.name = payload["name"].strip()
    row.employee_no = payload["employeeNo"].strip()
    row.id_card_no = payload.get("idCardNo") or ""
    row.passport_no = payload.get("passportNo") or ""
    row.passport_expiry = payload.get("passportExpiry") or ""
    row.position = payload.get("position") or ""
    row.nationality = payload["nationality"].strip()
    row.workshop = DEFAULT_WORKSHOP
    row.team = payload["team"].strip()
    row.birth_date = payload.get("birthDate") or ""
    row.age = int(payload.get("age") or 0)
    row.gender = payload.get("gender") or ""
    row.ethnicity = payload.get("ethnicity") or ""
    row.native_place = payload.get("nativePlace") or ""
    row.education = payload.get("education") or ""
    row.home_address = payload.get("homeAddress") or ""
    row.graduation_school = payload.get("graduationSchool") or ""
    row.major = payload.get("major") or ""
    row.indonesia_phone = payload.get("indonesiaPhone") or ""
    row.domestic_phone = payload.get("domesticPhone") or ""
    row.dormitory_no = payload.get("dormitoryNo") or ""
    row.status = payload["status"].strip()
    db.session.commit()
    return row.to_dict(), None, 200


def delete_personnel(personnel_id: str) -> tuple[dict | None, str | None, int]:
    row = Personnel.query.get(personnel_id)
    if row is None:
        return None, "人员不存在", 404
    db.session.delete(row)
    db.session.commit()
    return {"id": personnel_id}, None, 200
