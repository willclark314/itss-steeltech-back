"""临时任务业务逻辑"""

from __future__ import annotations

import uuid
from datetime import datetime

from flask_jwt_extended import get_jwt
from sqlalchemy import or_

from app.services.auth_scope import is_jwt_admin
from steeltech_db.extensions import db
from steeltech_db.models import Personnel, Project, TempTask, TempTaskPersonnel


def _now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def _get_editor_personnel_id() -> str | None:
    try:
        claims = get_jwt()
    except RuntimeError:
        return None
    personnel_id = claims.get("personnel_id")
    return str(personnel_id).strip() if personnel_id else None


def _can_access_personnel(target_personnel_id: str) -> bool:
    editor_id = _get_editor_personnel_id()
    if not editor_id:
        return False
    if editor_id == target_personnel_id:
        return True
    return is_jwt_admin()


def _can_edit_task(task: TempTask) -> bool:
    editor_id = _get_editor_personnel_id()
    if not editor_id:
        return False
    if task.created_by == editor_id:
        return True
    if is_jwt_admin():
        return True
    associated = (
        TempTaskPersonnel.query.filter_by(temp_task_id=task.id, personnel_id=editor_id).first()
    )
    return associated is not None


def _normalize_date(value: str | None) -> str:
    """兼容历史 YYYY-MM-DD HH:mm:ss，统一落地 YYYY-MM-DD。"""
    normalized = (value or "").strip()
    return normalized[:10] if normalized else ""


def _validate_date(value: str | None, *, field_name: str, required: bool = False) -> str | None:
    normalized = _normalize_date(value)
    if not normalized:
        if required:
            return f"{field_name}不能为空"
        return None
    try:
        datetime.strptime(normalized, "%Y-%m-%d")
    except ValueError:
        return f"{field_name}格式无效，应为 YYYY-MM-DD"
    return None


def _normalize_personnel_ids(personnel_ids: list[str] | None) -> list[str]:
    return list(dict.fromkeys(item.strip() for item in (personnel_ids or []) if item and item.strip()))


def _validate_personnel_ids(personnel_ids: list[str]) -> str | None:
    if not personnel_ids:
        return "至少关联一名人员"
    found = {p.id for p in Personnel.query.filter(Personnel.id.in_(personnel_ids)).all()}
    missing = [item for item in personnel_ids if item not in found]
    if missing:
        return "关联人员不存在"
    return None


def _normalize_project_no(value: str | None) -> str:
    return (value or "").strip()


def _project_exists(project_no: str) -> bool:
    if not project_no:
        return False
    return Project.query.filter_by(project_no=project_no).first() is not None


def _get_personnel_names(personnel_ids: list[str]) -> dict[str, str]:
    if not personnel_ids:
        return {}
    personnel = Personnel.query.filter(Personnel.id.in_(personnel_ids)).all()
    return {p.id: p.name for p in personnel}


def _get_task_personnel_map(task_ids: list[str]) -> dict[str, list[str]]:
    if not task_ids:
        return {}
    links = (
        TempTaskPersonnel.query
        .filter(TempTaskPersonnel.temp_task_id.in_(task_ids))
        .order_by(TempTaskPersonnel.personnel_id)
        .all()
    )
    result: dict[str, list[str]] = {task_id: [] for task_id in task_ids}
    for link in links:
        result.setdefault(link.temp_task_id, []).append(link.personnel_id)
    return result


def _serialize_task(task: TempTask, personnel_map: dict[str, list[str]], name_map: dict[str, str]) -> dict:
    personnel_ids = personnel_map.get(task.id, [])
    payload = task.to_dict(
        personnel_ids=personnel_ids,
        created_by_name=name_map.get(task.created_by, ""),
    )
    payload["personnelNames"] = [name_map.get(item, item) for item in personnel_ids]
    return payload


def list_temp_tasks(*, personnel_id: str = "") -> tuple[list[dict] | None, str | None, int]:
    target_id = personnel_id.strip()
    if not target_id:
        return None, "请提供 personnelId 参数", 400
    if not _can_access_personnel(target_id):
        return None, "无权限查看该人员的临时任务", 403

    rows = (
        TempTask.query.filter(
            or_(
                TempTask.created_by == target_id,
                TempTask.id.in_(
                    db.session.query(TempTaskPersonnel.temp_task_id).filter_by(personnel_id=target_id)
                ),
            )
        )
        .order_by(TempTask.start_time.desc(), TempTask.created_at.desc())
        .all()
    )

    task_ids = [row.id for row in rows]
    personnel_map = _get_task_personnel_map(task_ids)
    all_personnel_ids = {row.created_by for row in rows}
    for ids in personnel_map.values():
        all_personnel_ids.update(ids)
    name_map = _get_personnel_names(list(all_personnel_ids))
    return [_serialize_task(row, personnel_map, name_map) for row in rows], None, 200


def create_temp_task(data: dict) -> tuple[dict | None, str | None, int]:
    editor_id = _get_editor_personnel_id()
    if not editor_id:
        return None, "无法识别当前用户", 401

    name = str(data.get("name", "")).strip()
    if not name:
        return None, "任务名称不能为空", 400

    start_time = _normalize_date(str(data.get("startTime", "")).strip() or _today_str())
    completed_at = _normalize_date(str(data.get("completedAt", "")).strip())
    description = str(data.get("description", "")).strip()
    personnel_ids = _normalize_personnel_ids(data.get("personnelIds"))
    is_related_project = bool(data.get("isRelatedProject"))
    related_project_no = _normalize_project_no(data.get("relatedProjectNo"))
    if editor_id not in personnel_ids:
        personnel_ids.insert(0, editor_id)

    for field_name, value, required in (("开始时间", start_time, True), ("完成时间", completed_at, False)):
        error = _validate_date(value, field_name=field_name, required=required)
        if error:
            return None, error, 400

    personnel_error = _validate_personnel_ids(personnel_ids)
    if personnel_error:
        return None, personnel_error, 400

    if is_related_project:
        if not related_project_no:
            return None, "关联项目号不能为空", 400
        if not _project_exists(related_project_no):
            return None, "关联项目不存在", 400
    else:
        related_project_no = ""

    now = _now_str()
    task_id = uuid.uuid4().hex[:12]
    task = TempTask(
        id=task_id,
        name=name,
        description=description,
        start_time=start_time,
        completed_at=completed_at or None,
        is_related_project=1 if is_related_project else 0,
        related_project_no=related_project_no or None,
        created_by=editor_id,
        created_at=now,
        updated_at=now,
    )
    db.session.add(task)
    for personnel_id in personnel_ids:
        db.session.add(
            TempTaskPersonnel(
                temp_task_id=task_id,
                personnel_id=personnel_id,
                created_at=now,
            )
        )
    db.session.commit()

    name_map = _get_personnel_names([editor_id, *personnel_ids])
    return _serialize_task(task, {task_id: personnel_ids}, name_map), None, 201


def update_temp_task(task_id: str, data: dict) -> tuple[dict | None, str | None, int]:
    task = TempTask.query.get(task_id.strip())
    if task is None:
        return None, "任务不存在", 404
    if not _can_edit_task(task):
        return None, "无权限修改该任务", 403

    name = str(data.get("name", task.name)).strip()
    if not name:
        return None, "任务名称不能为空", 400

    start_time = _normalize_date(str(data.get("startTime", task.start_time)).strip())
    completed_at = _normalize_date(str(data.get("completedAt", task.completed_at or "")).strip())
    description = str(data.get("description", task.description or "")).strip()
    personnel_ids = _normalize_personnel_ids(data.get("personnelIds"))
    is_related_project = bool(data.get("isRelatedProject", bool(task.is_related_project)))
    related_project_no = _normalize_project_no(data.get("relatedProjectNo", task.related_project_no or ""))
    if not personnel_ids:
        personnel_ids = [
            row.personnel_id
            for row in TempTaskPersonnel.query.filter_by(temp_task_id=task.id).all()
        ]
    if task.created_by not in personnel_ids:
        personnel_ids.insert(0, task.created_by)

    for field_name, value, required in (("开始时间", start_time, True), ("完成时间", completed_at, False)):
        error = _validate_date(value, field_name=field_name, required=required)
        if error:
            return None, error, 400

    personnel_error = _validate_personnel_ids(personnel_ids)
    if personnel_error:
        return None, personnel_error, 400

    if is_related_project:
        if not related_project_no:
            return None, "关联项目号不能为空", 400
        if not _project_exists(related_project_no):
            return None, "关联项目不存在", 400
    else:
        related_project_no = ""

    task.name = name
    task.description = description
    task.start_time = start_time
    task.completed_at = completed_at or None
    task.is_related_project = 1 if is_related_project else 0
    task.related_project_no = related_project_no or None
    task.updated_at = _now_str()

    TempTaskPersonnel.query.filter_by(temp_task_id=task.id).delete()
    now = _now_str()
    for personnel_id in personnel_ids:
        db.session.add(
            TempTaskPersonnel(
                temp_task_id=task.id,
                personnel_id=personnel_id,
                created_at=now,
            )
        )
    db.session.commit()

    name_map = _get_personnel_names([task.created_by, *personnel_ids])
    return _serialize_task(task, {task.id: personnel_ids}, name_map), None, 200


def delete_temp_task(task_id: str) -> tuple[dict | None, str | None, int]:
    task = TempTask.query.get(task_id.strip())
    if task is None:
        return None, "任务不存在", 404
    if not _can_edit_task(task):
        return None, "无权限删除该任务", 403

    deleted_id = task.id
    db.session.delete(task)
    db.session.commit()
    return {"id": deleted_id}, None, 200
