from __future__ import annotations

import json
from datetime import datetime

from steeltech_db.extensions import db
from steeltech_db.models import SystemSetting
from steeltech_db.navigation_defaults import (
    ALWAYS_VISIBLE_PAGES,
    DEFAULT_NAVIGATION_PAGES,
    DEFAULT_NAVIGATION_SYSTEMS,
    NAVIGATION_ORDER_KEY,
    VALID_NAVIGATION_SYSTEMS,
    NavigationOrderConfig,
    get_default_navigation_order,
)
from steeltech_db.permission_catalog import PAGE_ORDER_MAP


def _normalize_page_keys(raw_pages, *, known_pages: set[str]) -> list[str]:
    pages: list[str] = []
    seen_pages: set[str] = set()
    for raw in raw_pages or []:
        page_key = str(raw).strip()
        if page_key not in known_pages or page_key in seen_pages:
            continue
        seen_pages.add(page_key)
        pages.append(page_key)
    return pages


def normalize_navigation_order(payload: dict | NavigationOrderConfig | None) -> NavigationOrderConfig:
    if payload is None:
        return get_default_navigation_order()

    if isinstance(payload, NavigationOrderConfig):
        raw_systems = payload.systems
        raw_pages = payload.pages
        raw_hidden_pages = payload.hidden_pages
    else:
        raw_systems = payload.get("systems")
        raw_pages = payload.get("pages")
        raw_hidden_pages = payload.get("hiddenPages")
        if raw_hidden_pages is None:
            raw_hidden_pages = payload.get("hidden_pages")

    known_pages = set(PAGE_ORDER_MAP.keys())

    systems: list[str] = []
    seen_systems: set[str] = set()
    for raw in raw_systems or []:
        system_id = str(raw).strip()
        if system_id not in VALID_NAVIGATION_SYSTEMS or system_id in seen_systems:
            continue
        seen_systems.add(system_id)
        systems.append(system_id)
    for system_id in DEFAULT_NAVIGATION_SYSTEMS:
        if system_id not in seen_systems:
            systems.append(system_id)

    pages = _normalize_page_keys(raw_pages, known_pages=known_pages)
    for page_key in DEFAULT_NAVIGATION_PAGES:
        if page_key not in pages:
            pages.append(page_key)

    hidden_pages = [
        page_key
        for page_key in _normalize_page_keys(raw_hidden_pages, known_pages=known_pages)
        if page_key not in ALWAYS_VISIBLE_PAGES
    ]

    return NavigationOrderConfig(systems=systems, pages=pages, hidden_pages=hidden_pages)


def get_navigation_order() -> dict:
    row = SystemSetting.query.filter_by(key=NAVIGATION_ORDER_KEY).first()
    if row and row.value:
        try:
            parsed = json.loads(row.value)
            return normalize_navigation_order(parsed).to_dict()
        except (TypeError, json.JSONDecodeError):
            pass
    return get_default_navigation_order().to_dict()


def save_navigation_order(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("请求体格式错误")

    normalized = normalize_navigation_order(payload).to_dict()
    row = SystemSetting.query.filter_by(key=NAVIGATION_ORDER_KEY).first()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    value = json.dumps(normalized, ensure_ascii=False)

    if row is None:
        row = SystemSetting(key=NAVIGATION_ORDER_KEY, value=value, updated_at=now)
        db.session.add(row)
    else:
        row.value = value
        row.updated_at = now

    db.session.commit()
    return normalized
