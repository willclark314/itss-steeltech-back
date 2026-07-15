from __future__ import annotations

from datetime import datetime

from steeltech_db.extensions import db
from steeltech_db.models import ProjectDesignWorkflow


def _now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def needs_design_workflow(natures: list[str]) -> bool:
    return "design" in natures


def map_design_workflow(row: ProjectDesignWorkflow | None) -> dict | None:
    if row is None:
        return None
    return {
        "designStartedAt": (row.design_started_at or "").strip(),
        "designCompletedAt": (row.design_completed_at or "").strip(),
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


def _normalize_workflow_datetime(value) -> str | None:
    text_value = (value or "").strip()
    return text_value or None


def update_design_workflow(
    project_no: str,
    payload: dict,
    natures: list[str],
) -> tuple[ProjectDesignWorkflow | None, str | None]:
    if not needs_design_workflow(natures):
        return None, "当前项目不适用设计流程"

    workflow = ensure_design_workflow(project_no, natures)
    assert workflow is not None

    workflow.design_started_at = _normalize_workflow_datetime(payload.get("designStartedAt"))
    workflow.design_completed_at = _normalize_workflow_datetime(payload.get("designCompletedAt"))
    workflow.updated_at = _now_text()
    return workflow, None


def mark_design_completed(workflow: ProjectDesignWorkflow) -> None:
    """补齐设计开始/完成时间，表示设计进度已完成。"""
    now = _now_text()
    if not (workflow.design_started_at or "").strip():
        workflow.design_started_at = now
    if not (workflow.design_completed_at or "").strip():
        workflow.design_completed_at = now
    workflow.updated_at = now
