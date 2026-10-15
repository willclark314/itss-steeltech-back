"""项目模型管理服务"""

from __future__ import annotations

import math
import uuid
from datetime import datetime

from sqlalchemy import or_

from steeltech_db.extensions import db
from steeltech_db.models.project import Project
from steeltech_db.models.project_model import ProjectModel

MODEL_TYPES = frozenset({"detail", "jiagong"})
MODEL_STATUSES = frozenset({"not_started", "in_progress", "completed"})


def _now_local() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _generate_id() -> str:
    return f"pm_{uuid.uuid4().hex[:14]}"


def _row_to_dict(row: ProjectModel, project: Project | None = None) -> dict:
    if project is None:
        project = Project.query.get(row.project_no)
    return row.to_dict(
        project_name=(project.name if project else ""),
        is_jiagongdan=bool(project.is_jiagongdan) if project else False,
    )


def _parse_weight(value) -> float | None:
    if value is None or value == "":
        return None
    try:
        weight = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError("模型重量必须为数字") from exc
    if weight < 0:
        raise ValueError("模型重量不能为负数")
    return weight


def _validate_payload(payload: dict, *, partial: bool = False) -> dict:
    data: dict = {}

    if not partial or "projectNo" in payload:
        project_no = str(payload.get("projectNo") or "").strip()
        if not project_no:
            raise ValueError("请选择关联项目")
        if not Project.query.get(project_no):
            raise ValueError(f"项目不存在：{project_no}")
        data["project_no"] = project_no

    if not partial or "modelType" in payload:
        model_type = str(payload.get("modelType") or "").strip()
        if model_type not in MODEL_TYPES:
            raise ValueError("模型类型无效，请选择细化模型或甲供模型")
        data["model_type"] = model_type

    if not partial or "name" in payload:
        name = str(payload.get("name") or "").strip()
        if not name:
            raise ValueError("模型名称不能为空")
        data["name"] = name

    if not partial or "status" in payload:
        status = str(payload.get("status") or "not_started").strip()
        if status not in MODEL_STATUSES:
            raise ValueError("模型状态无效")
        data["status"] = status

    if not partial or "modelWeightTons" in payload:
        data["model_weight_tons"] = _parse_weight(payload.get("modelWeightTons"))

    if not partial or "modelPath" in payload:
        data["model_path"] = str(payload.get("modelPath") or "").strip() or None

    if not partial or "remark" in payload:
        data["remark"] = str(payload.get("remark") or "").strip() or None

    if not partial or "seq" in payload:
        seq_raw = payload.get("seq")
        if seq_raw is None or seq_raw == "":
            data["seq"] = 0
        else:
            try:
                data["seq"] = int(seq_raw)
            except (TypeError, ValueError) as exc:
                raise ValueError("排序号必须为整数") from exc

    return data


def list_project_models(
    *,
    keyword: str = "",
    model_type: str = "",
    status: str = "",
    project_no: str = "",
    page: int = 1,
    page_size: int = 20,
) -> dict:
    query = (
        db.session.query(ProjectModel, Project)
        .outerjoin(Project, Project.project_no == ProjectModel.project_no)
    )

    kw = (keyword or "").strip()
    if kw:
        like = f"%{kw}%"
        query = query.filter(
            or_(
                ProjectModel.project_no.ilike(like),
                ProjectModel.name.ilike(like),
                ProjectModel.model_path.ilike(like),
                ProjectModel.remark.ilike(like),
                Project.name.ilike(like),
            )
        )

    mt = (model_type or "").strip()
    if mt:
        if mt not in MODEL_TYPES:
            raise ValueError("模型类型无效")
        query = query.filter(ProjectModel.model_type == mt)

    st = (status or "").strip()
    if st:
        if st not in MODEL_STATUSES:
            raise ValueError("模型状态无效")
        query = query.filter(ProjectModel.status == st)

    pn = (project_no or "").strip()
    if pn:
        query = query.filter(ProjectModel.project_no == pn)

    total = query.count()
    page = max(1, int(page or 1))
    page_size = max(1, min(200, int(page_size or 20)))
    total_pages = max(1, math.ceil(total / page_size)) if total else 1
    if page > total_pages:
        page = total_pages

    rows = (
        query.order_by(
            ProjectModel.project_no.asc(),
            ProjectModel.seq.asc(),
            ProjectModel.created_at.desc(),
            ProjectModel.id.desc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return {
        "list": [_row_to_dict(model, project) for model, project in rows],
        "total": total,
        "page": page,
        "pageSize": page_size,
        "totalPages": total_pages,
    }


def get_project_model(model_id: str) -> dict | None:
    row = ProjectModel.query.get(model_id)
    if not row:
        return None
    return _row_to_dict(row)


def create_project_model(payload: dict) -> dict:
    data = _validate_payload(payload, partial=False)
    now = _now_local()
    row = ProjectModel(
        id=_generate_id(),
        project_no=data["project_no"],
        model_type=data["model_type"],
        name=data["name"],
        status=data.get("status", "not_started"),
        model_weight_tons=data.get("model_weight_tons"),
        model_path=data.get("model_path"),
        remark=data.get("remark"),
        seq=data.get("seq", 0),
        created_at=now,
        updated_at=now,
    )
    db.session.add(row)
    db.session.commit()
    return _row_to_dict(row)


def update_project_model(model_id: str, payload: dict) -> tuple[dict | None, str | None, int]:
    row = ProjectModel.query.get(model_id)
    if not row:
        return None, "项目模型不存在", 404

    try:
        data = _validate_payload(payload, partial=True)
    except ValueError as exc:
        return None, str(exc), 400

    for key, value in data.items():
        setattr(row, key, value)
    row.updated_at = _now_local()
    db.session.commit()
    return _row_to_dict(row), None, 200


def delete_project_model(model_id: str) -> tuple[bool, str | None, int]:
    row = ProjectModel.query.get(model_id)
    if not row:
        return False, "项目模型不存在", 404
    db.session.delete(row)
    db.session.commit()
    return True, None, 200
