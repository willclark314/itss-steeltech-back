from __future__ import annotations

from datetime import datetime

from flask_jwt_extended import get_jwt

from steeltech_db.extensions import db
from steeltech_db.models import ProjectDesignWorkflow


def _now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _today_text() -> str:
    return datetime.now().strftime("%Y-%m-%d")


def needs_design_workflow(natures: list[str]) -> bool:
    return "design" in natures


def _to_date_only(value: str | None) -> str:
    """将设计开始/结束规范为 YYYY-MM-DD（兼容历史带时分秒的值）。"""
    text_value = (value or "").strip()
    if not text_value:
        return ""
    if len(text_value) >= 10 and text_value[4:5] == "-" and text_value[7:8] == "-":
        return text_value[:10]
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y/%m/%d", "%Y-%m-%d"):
        try:
            return datetime.strptime(text_value, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return text_value


def map_design_workflow(
    row: ProjectDesignWorkflow | None,
    *,
    updated_by_name: str = "",
) -> dict | None:
    if row is None:
        return None
    return {
        "designStartedAt": _to_date_only(row.design_started_at),
        "designCompletedAt": _to_date_only(row.design_completed_at),
        "designAreaSqm": row.design_area_sqm,
        "designAreaUpdatedAt": (row.design_area_updated_at or "").strip(),
        "designAreaUpdatedBy": (row.design_area_updated_by or "").strip(),
        "designAreaUpdatedByName": updated_by_name,
    }


def get_design_workflow(project_no: str) -> ProjectDesignWorkflow | None:
    return ProjectDesignWorkflow.query.get(project_no)


def _get_workflows_map(project_nos: list[str]) -> dict[str, ProjectDesignWorkflow]:
    if not project_nos:
        return {}
    rows = ProjectDesignWorkflow.query.filter(
        ProjectDesignWorkflow.project_no.in_(project_nos)
    ).all()
    return {row.project_no: row for row in rows}


def get_design_workflows_map(project_nos: list[str]) -> dict[str, dict | None]:
    workflows = _get_workflows_map(project_nos)
    return {project_no: map_design_workflow(workflows.get(project_no)) for project_no in project_nos}


def get_workflows_orm_map(project_nos: list[str]) -> dict[str, ProjectDesignWorkflow]:
    return _get_workflows_map(project_nos)


def ensure_design_workflow(project_no: str, natures: list[str]) -> ProjectDesignWorkflow | None:
    if not needs_design_workflow(natures):
        delete_design_workflow(project_no)
        return None

    workflow = get_design_workflow(project_no)
    if workflow is None:
        workflow = ProjectDesignWorkflow(project_no=project_no)
        db.session.add(workflow)
        return workflow

    workflow.updated_at = _now_text()
    return workflow


def delete_design_workflow(project_no: str) -> None:
    workflow = get_design_workflow(project_no)
    if workflow is not None:
        db.session.delete(workflow)


def _normalize_workflow_date(value) -> str | None:
    date_only = _to_date_only(value if isinstance(value, str) else str(value or ""))
    return date_only or None


def update_design_workflow(
    project_no: str,
    payload: dict,
    natures: list[str],
) -> tuple[ProjectDesignWorkflow | None, str | None]:
    if not needs_design_workflow(natures):
        return None, "当前项目不适用设计流程"

    workflow = ensure_design_workflow(project_no, natures)
    assert workflow is not None

    workflow.design_started_at = _normalize_workflow_date(payload.get("designStartedAt"))
    workflow.design_completed_at = _normalize_workflow_date(payload.get("designCompletedAt"))
    workflow.updated_at = _now_text()
    return workflow, None


def mark_design_completed(workflow: ProjectDesignWorkflow) -> None:
    """补齐设计开始/完成日期，表示设计进度已完成。"""
    today = _today_text()
    if not (workflow.design_started_at or "").strip():
        workflow.design_started_at = today
    else:
        workflow.design_started_at = _to_date_only(workflow.design_started_at)
    if not (workflow.design_completed_at or "").strip():
        workflow.design_completed_at = today
    else:
        workflow.design_completed_at = _to_date_only(workflow.design_completed_at)
    workflow.updated_at = _now_text()


def clear_design_completed(workflow: ProjectDesignWorkflow) -> None:
    """取消设计完成标记，保留开始日期。"""
    workflow.design_completed_at = ""
    workflow.updated_at = _now_text()


def _get_jwt_personnel_id() -> str | None:
    try:
        claims = get_jwt()
    except RuntimeError:
        return None
    personnel_id = (claims.get("personnel_id") or "").strip()
    return personnel_id or None


def _normalize_design_area_sqm(value) -> tuple[float | None, str | None]:
    if value is None or value == "":
        return None, None
    try:
        area = float(value)
    except (TypeError, ValueError):
        return None, "设计面积格式无效"
    if area < 0:
        return None, "设计面积不能为负数"
    return round(area, 2), None


def _touch_design_area_audit(workflow: ProjectDesignWorkflow, updated_by: str | None) -> None:
    workflow.design_area_updated_at = _now_text()
    workflow.design_area_updated_by = updated_by


def update_design_area(
    project_no: str,
    design_area_sqm,
    natures: list[str],
    *,
    updated_by: str | None = None,
) -> tuple[ProjectDesignWorkflow | None, str | None]:
    if not needs_design_workflow(natures):
        return None, "当前项目不适用设计流程"

    area, error = _normalize_design_area_sqm(design_area_sqm)
    if error:
        return None, error

    workflow = ensure_design_workflow(project_no, natures)
    assert workflow is not None

    previous = workflow.design_area_sqm
    if previous == area:
        return workflow, None

    workflow.design_area_sqm = area
    _touch_design_area_audit(workflow, updated_by)
    workflow.updated_at = _now_text()
    return workflow, None


def update_design_area_from_request(
    project_no: str,
    payload: dict,
    natures: list[str],
) -> tuple[ProjectDesignWorkflow | None, str | None]:
    return update_design_area(
        project_no,
        payload.get("designAreaSqm"),
        natures,
        updated_by=_get_jwt_personnel_id(),
    )
