from __future__ import annotations

import json
from datetime import datetime

from flask_jwt_extended import get_jwt_identity

from steeltech_db.extensions import db
from steeltech_db.models.user_preference import UserPreference

MEMBER_ORDER_PREFERENCE_KEY = "detail_team_member_order"


def _get_account() -> str:
    return str(get_jwt_identity() or "").strip()


def _normalize_personnel_ids(raw: object) -> list[str] | None:
    if not isinstance(raw, list):
        return None

    personnel_ids: list[str] = []
    for item in raw:
        if not isinstance(item, str):
            return None
        normalized = item.strip()
        if not normalized:
            return None
        personnel_ids.append(normalized)

    return list(dict.fromkeys(personnel_ids))


def get_member_order() -> tuple[dict | None, str | None, int]:
    account = _get_account()
    if not account:
        return None, "请先登录", 401

    row = UserPreference.query.filter_by(
        account=account,
        preference_key=MEMBER_ORDER_PREFERENCE_KEY,
    ).first()
    if row is None:
        return {"personnelIds": []}, None, 200

    try:
        parsed = json.loads(row.preference_value)
    except json.JSONDecodeError:
        return {"personnelIds": []}, None, 200

    personnel_ids = _normalize_personnel_ids(parsed)
    if personnel_ids is None:
        return {"personnelIds": []}, None, 200

    return {"personnelIds": personnel_ids}, None, 200


def save_member_order(payload: dict) -> tuple[dict | None, str | None, int]:
    account = _get_account()
    if not account:
        return None, "请先登录", 401

    personnel_ids = _normalize_personnel_ids(payload.get("personnelIds"))
    if personnel_ids is None:
        return None, "人员顺序格式不正确", 400

    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    value = json.dumps(personnel_ids, ensure_ascii=False)
    row = UserPreference.query.filter_by(
        account=account,
        preference_key=MEMBER_ORDER_PREFERENCE_KEY,
    ).first()

    if row is None:
        db.session.add(
            UserPreference(
                account=account,
                preference_key=MEMBER_ORDER_PREFERENCE_KEY,
                preference_value=value,
                updated_at=now,
            )
        )
    else:
        row.preference_value = value
        row.updated_at = now

    db.session.commit()
    return {"personnelIds": personnel_ids}, None, 200
