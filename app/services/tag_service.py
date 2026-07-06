from __future__ import annotations

import uuid

from sqlalchemy import text

from steeltech_db.extensions import db


def _map_tag_row(row) -> dict:
    return {"id": row.id, "name": row.name}


def list_tags() -> list[dict]:
    rows = db.session.execute(text("SELECT id, name FROM tags ORDER BY name COLLATE NOCASE")).all()
    return [_map_tag_row(row) for row in rows]


def get_tag_by_id(tag_id: str) -> dict | None:
    row = db.session.execute(
        text("SELECT id, name FROM tags WHERE id = :id"),
        {"id": tag_id},
    ).first()
    return _map_tag_row(row) if row else None


def create_tag(name: str) -> dict:
    normalized = name.strip()
    if not normalized:
        raise ValueError("标签名称不能为空")
    existing = db.session.execute(
        text("SELECT id, name FROM tags WHERE name = :name"),
        {"name": normalized},
    ).first()
    if existing:
        return _map_tag_row(existing)
    tag_id = uuid.uuid4().hex[:12]
    db.session.execute(
        text("INSERT INTO tags (id, name) VALUES (:id, :name)"),
        {"id": tag_id, "name": normalized},
    )
    db.session.commit()
    return {"id": tag_id, "name": normalized}


def parse_tags_param(raw: str) -> list[str]:
    return list(dict.fromkeys(item.strip() for item in (raw or "").split(",") if item.strip()))


def normalize_tag_ids(tag_ids: list[str] | None) -> tuple[list[str], str | None]:
    unique = list(dict.fromkeys(item.strip() for item in (tag_ids or []) if item and item.strip()))
    if not unique:
        return [], None
    placeholders = ", ".join(f":t{i}" for i in range(len(unique)))
    params = {f"t{i}": value for i, value in enumerate(unique)}
    rows = db.session.execute(
        text(f"SELECT id FROM tags WHERE id IN ({placeholders})"),
        params,
    ).all()
    found = {row.id for row in rows}
    missing = [item for item in unique if item not in found]
    if missing:
        return [], "标签不存在"
    return unique, None


def get_project_tags(project_no: str) -> list[dict]:
    rows = db.session.execute(
        text(
            """
            SELECT t.id, t.name
            FROM project_tags pt
            INNER JOIN tags t ON t.id = pt.tag_id
            WHERE pt.project_no = :project_no
            ORDER BY t.name COLLATE NOCASE
            """
        ),
        {"project_no": project_no},
    ).all()
    return [_map_tag_row(row) for row in rows]


def get_contact_tags(contact_form_id: str) -> list[dict]:
    rows = db.session.execute(
        text(
            """
            SELECT t.id, t.name
            FROM contact_form_tags cft
            INNER JOIN tags t ON t.id = cft.tag_id
            WHERE cft.contact_form_id = :contact_form_id
            ORDER BY t.name COLLATE NOCASE
            """
        ),
        {"contact_form_id": contact_form_id},
    ).all()
    return [_map_tag_row(row) for row in rows]


def get_project_tags_map(project_nos: list[str]) -> dict[str, list[dict]]:
    if not project_nos:
        return {}
    placeholders = ", ".join(f":p{i}" for i in range(len(project_nos)))
    params = {f"p{i}": value for i, value in enumerate(project_nos)}
    rows = db.session.execute(
        text(
            f"""
            SELECT pt.project_no, t.id, t.name
            FROM project_tags pt
            INNER JOIN tags t ON t.id = pt.tag_id
            WHERE pt.project_no IN ({placeholders})
            ORDER BY t.name COLLATE NOCASE
            """
        ),
        params,
    ).all()
    result: dict[str, list[dict]] = {project_no: [] for project_no in project_nos}
    for row in rows:
        result.setdefault(row.project_no, []).append({"id": row.id, "name": row.name})
    return result


def get_contact_tags_map(contact_ids: list[str]) -> dict[str, list[dict]]:
    if not contact_ids:
        return {}
    placeholders = ", ".join(f":c{i}" for i in range(len(contact_ids)))
    params = {f"c{i}": value for i, value in enumerate(contact_ids)}
    rows = db.session.execute(
        text(
            f"""
            SELECT cft.contact_form_id, t.id, t.name
            FROM contact_form_tags cft
            INNER JOIN tags t ON t.id = cft.tag_id
            WHERE cft.contact_form_id IN ({placeholders})
            ORDER BY t.name COLLATE NOCASE
            """
        ),
        params,
    ).all()
    result: dict[str, list[dict]] = {contact_id: [] for contact_id in contact_ids}
    for row in rows:
        result.setdefault(row.contact_form_id, []).append({"id": row.id, "name": row.name})
    return result


def sync_project_tags(project_no: str, tag_ids: list[str]) -> None:
    db.session.execute(
        text("DELETE FROM project_tags WHERE project_no = :project_no"),
        {"project_no": project_no},
    )
    for tag_id in tag_ids:
        db.session.execute(
            text(
                "INSERT OR IGNORE INTO project_tags (project_no, tag_id) "
                "VALUES (:project_no, :tag_id)"
            ),
            {"project_no": project_no, "tag_id": tag_id},
        )


def sync_contact_tags(contact_form_id: str, tag_ids: list[str]) -> None:
    db.session.execute(
        text("DELETE FROM contact_form_tags WHERE contact_form_id = :contact_form_id"),
        {"contact_form_id": contact_form_id},
    )
    for tag_id in tag_ids:
        db.session.execute(
            text(
                "INSERT OR IGNORE INTO contact_form_tags (contact_form_id, tag_id) "
                "VALUES (:contact_form_id, :tag_id)"
            ),
            {"contact_form_id": contact_form_id, "tag_id": tag_id},
        )


def build_tag_exists_clause(
    *,
    entity_id_column: str,
    join_table: str,
    join_entity_column: str,
    tag_ids: list[str],
    param_prefix: str = "filter_tag",
) -> tuple[str, dict]:
    if not tag_ids:
        return "", {}
    placeholders = ", ".join(f":{param_prefix}{i}" for i in range(len(tag_ids)))
    params = {f"{param_prefix}{i}": value for i, value in enumerate(tag_ids)}
    clause = f"""EXISTS (
      SELECT 1 FROM {join_table} jt
      WHERE jt.{join_entity_column} = {entity_id_column}
        AND jt.tag_id IN ({placeholders})
    )"""
    return clause, params
