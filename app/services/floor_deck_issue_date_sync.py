"""排楼承板发图时间：设计发图计划 ↔ 细化发图计划 双向同步"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from steeltech_db.extensions import db


def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _project_key(project_no: str | None) -> str:
    return str(project_no or "").strip().upper()


def _floor_deck_tuple(row: Any) -> tuple[str | None, str | None]:
    return (
        getattr(row, "floor_deck_planned_issue_date", None) or None,
        getattr(row, "floor_deck_actual_issue_date", None) or None,
    )


def _prefer_newer(left: Any, right: Any) -> Any:
    """按 updated_at 取较新的一行；相同时优先 left。"""
    left_updated = str(getattr(left, "updated_at", None) or "")
    right_updated = str(getattr(right, "updated_at", None) or "")
    return right if right_updated > left_updated else left


def existing_project_nos(model: type, year: int, month: int) -> set[str]:
    rows = model.query.filter_by(year=year, month=month).all()
    return {_project_key(row.project_no) for row in rows if _project_key(row.project_no)}


def build_peer_floor_deck_map(
    peer_model: type,
    year: int,
    month: int,
) -> dict[str, tuple[str | None, str | None]]:
    rows = peer_model.query.filter_by(year=year, month=month).all()
    result: dict[str, tuple[str | None, str | None]] = {}
    for row in rows:
        key = _project_key(row.project_no)
        if not key:
            continue
        result[key] = _floor_deck_tuple(row)
    return result


def inherit_floor_deck_for_new_projects(
    payloads: list[dict],
    *,
    year: int,
    month: int,
    peer_model: type,
    existing_nos: set[str],
) -> None:
    """本月新加入的项目若楼承板时间为空，从对端同月同项目继承。"""
    peer_map = build_peer_floor_deck_map(peer_model, year, month)
    if not peer_map:
        return

    for payload in payloads:
        key = _project_key(payload.get("project_no"))
        if not key or key in existing_nos:
            continue
        peer_planned, peer_actual = peer_map.get(key, (None, None))
        if payload.get("floor_deck_planned_issue_date") is None and peer_planned:
            payload["floor_deck_planned_issue_date"] = peer_planned
        if payload.get("floor_deck_actual_issue_date") is None and peer_actual:
            payload["floor_deck_actual_issue_date"] = peer_actual


def sync_floor_deck_to_peer(
    payloads: list[dict],
    *,
    year: int,
    month: int,
    peer_model: type,
) -> None:
    """把本侧保存的排楼承板时间写到对端同月同项目行（仅更新已存在行）。"""
    if not payloads:
        return

    peer_rows = peer_model.query.filter_by(year=year, month=month).all()
    if not peer_rows:
        return

    peer_by_no: dict[str, list[Any]] = {}
    for row in peer_rows:
        key = _project_key(row.project_no)
        if not key:
            continue
        peer_by_no.setdefault(key, []).append(row)

    now = _now_str()
    changed = False
    for payload in payloads:
        key = _project_key(payload.get("project_no"))
        if not key:
            continue
        targets = peer_by_no.get(key) or []
        planned = payload.get("floor_deck_planned_issue_date")
        actual = payload.get("floor_deck_actual_issue_date")
        for target in targets:
            if (
                target.floor_deck_planned_issue_date == planned
                and target.floor_deck_actual_issue_date == actual
            ):
                continue
            target.floor_deck_planned_issue_date = planned
            target.floor_deck_actual_issue_date = actual
            target.updated_at = now
            changed = True

    if changed:
        db.session.flush()


def enrich_records_with_peer_floor_deck(
    records: list[dict],
    *,
    year: int | None,
    month: int | None,
    self_model: type,
    peer_model: type,
) -> list[dict]:
    """列表展示时，同月同项目取两侧中 updated_at 较新的排楼承板时间。"""
    if not records:
        return records
    if year is None or month is None:
        # 跨月列表：按每条记录的年月分组处理
        grouped: dict[tuple[int, int], list[dict]] = {}
        for item in records:
            key = (int(item["year"]), int(item["month"]))
            grouped.setdefault(key, []).append(item)
        for (y, m), items in grouped.items():
            enrich_records_with_peer_floor_deck(
                items,
                year=y,
                month=m,
                self_model=self_model,
                peer_model=peer_model,
            )
        return records

    self_rows = self_model.query.filter_by(year=year, month=month).all()
    peer_rows = peer_model.query.filter_by(year=year, month=month).all()
    self_map = {_project_key(row.project_no): row for row in self_rows}
    peer_map = {_project_key(row.project_no): row for row in peer_rows}

    for item in records:
        key = _project_key(item.get("projectNo"))
        if not key:
            continue
        self_row = self_map.get(key)
        peer_row = peer_map.get(key)
        if not peer_row:
            continue
        chosen = _prefer_newer(self_row, peer_row) if self_row else peer_row
        planned, actual = _floor_deck_tuple(chosen)
        item["floorDeckPlannedIssueDate"] = planned
        item["floorDeckActualIssueDate"] = actual

    return records
