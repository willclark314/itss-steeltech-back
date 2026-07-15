from __future__ import annotations

import uuid

from steeltech_db.extensions import db
from steeltech_db.models.tag import ContactFormTag, ProjectTag, Tag


def _tag_to_dict(tag: Tag) -> dict:
    return {"id": tag.id, "name": tag.name}


def list_tags() -> list[dict]:
    tags = Tag.query.order_by(db.func.lower(Tag.name)).all()
    return [_tag_to_dict(t) for t in tags]


def get_tag_by_id(tag_id: str) -> dict | None:
    tag = Tag.query.get(tag_id)
    return _tag_to_dict(tag) if tag else None


def create_tag(name: str) -> dict:
    normalized = name.strip()
    if not normalized:
        raise ValueError("标签名称不能为空")
    existing = Tag.query.filter_by(name=normalized).first()
    if existing:
        return _tag_to_dict(existing)
    tag = Tag(id=uuid.uuid4().hex[:12], name=normalized)
    db.session.add(tag)
    db.session.commit()
    return _tag_to_dict(tag)


def parse_tags_param(raw: str) -> list[str]:
    return list(dict.fromkeys(item.strip() for item in (raw or "").split(",") if item.strip()))


def normalize_tag_ids(tag_ids: list[str] | None) -> tuple[list[str], str | None]:
    unique = list(dict.fromkeys(item.strip() for item in (tag_ids or []) if item and item.strip()))
    if not unique:
        return [], None
    found = {t.id for t in Tag.query.filter(Tag.id.in_(unique)).all()}
    missing = [item for item in unique if item not in found]
    if missing:
        return [], "标签不存在"
    return unique, None


def get_project_tags(project_no: str) -> list[dict]:
    tags = (
        db.session.query(Tag)
        .join(ProjectTag, ProjectTag.tag_id == Tag.id)
        .filter(ProjectTag.project_no == project_no)
        .order_by(db.func.lower(Tag.name))
        .all()
    )
    return [_tag_to_dict(t) for t in tags]


def get_contact_tags(contact_form_id: str) -> list[dict]:
    tags = (
        db.session.query(Tag)
        .join(ContactFormTag, ContactFormTag.tag_id == Tag.id)
        .filter(ContactFormTag.contact_form_id == contact_form_id)
        .order_by(db.func.lower(Tag.name))
        .all()
    )
    return [_tag_to_dict(t) for t in tags]


def get_project_tags_map(project_nos: list[str]) -> dict[str, list[dict]]:
    if not project_nos:
        return {}
    rows = (
        db.session.query(ProjectTag.project_no, Tag.id, Tag.name)
        .join(Tag, Tag.id == ProjectTag.tag_id)
        .filter(ProjectTag.project_no.in_(project_nos))
        .order_by(db.func.lower(Tag.name))
        .all()
    )
    result: dict[str, list[dict]] = {project_no: [] for project_no in project_nos}
    for row in rows:
        result.setdefault(row.project_no, []).append({"id": row.id, "name": row.name})
    return result


def get_contact_tags_map(contact_ids: list[str]) -> dict[str, list[dict]]:
    if not contact_ids:
        return {}
    rows = (
        db.session.query(ContactFormTag.contact_form_id, Tag.id, Tag.name)
        .join(Tag, Tag.id == ContactFormTag.tag_id)
        .filter(ContactFormTag.contact_form_id.in_(contact_ids))
        .order_by(db.func.lower(Tag.name))
        .all()
    )
    result: dict[str, list[dict]] = {contact_id: [] for contact_id in contact_ids}
    for row in rows:
        result.setdefault(row.contact_form_id, []).append({"id": row.id, "name": row.name})
    return result


def sync_project_tags(project_no: str, tag_ids: list[str]) -> None:
    ProjectTag.query.filter_by(project_no=project_no).delete()
    for tag_id in tag_ids:
        db.session.add(ProjectTag(project_no=project_no, tag_id=tag_id))
    db.session.commit()


def sync_contact_tags(contact_form_id: str, tag_ids: list[str]) -> None:
    ContactFormTag.query.filter_by(contact_form_id=contact_form_id).delete()
    for tag_id in tag_ids:
        db.session.add(ContactFormTag(contact_form_id=contact_form_id, tag_id=tag_id))
    db.session.commit()


# ── 以下为 query-builder 工具函数，供其他 service 构建动态 SQL 使用 ──


def build_tag_exists_clause(
    *,
    entity_id_column: str,
    join_table: str,
    join_entity_column: str,
    tag_ids: list[str],
    param_prefix: str = "filter_tag",
) -> tuple[str, dict]:
    """生成 EXISTS 子查询 SQL 片段（跨表标签过滤）。

    注意：此函数生成 raw SQL 片段嵌入到上层动态 WHERE 子句中，
    因为上层使用字符串拼接构建 {where_clause}，无法用 ORM。
    """
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
