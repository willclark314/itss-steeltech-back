from __future__ import annotations

from datetime import datetime

from flask_jwt_extended import get_jwt

from steeltech_db.extensions import db
from steeltech_db.models import ProjectDetailWorkflow

PHASE_STATUS_NOT_STARTED = "not_started"
PHASE_STATUS_IN_PROGRESS = "in_progress"
PHASE_STATUS_COMPLETED = "completed"
PHASE_STATUS_NOT_APPLICABLE = "not_applicable"

WORKFLOW_ACTION_START_MODELING = "start_modeling"
WORKFLOW_ACTION_COMPLETE_MODELING = "complete_modeling"
WORKFLOW_ACTION_RESET_MODELING = "reset_modeling"
WORKFLOW_ACTION_REOPEN_MODELING = "reopen_modeling"
WORKFLOW_ACTION_START_PLATE_LAYOUT = "start_plate_layout"
WORKFLOW_ACTION_COMPLETE_DRAWING = "complete_drawing"
WORKFLOW_ACTION_RESET_DRAWING = "reset_drawing"
WORKFLOW_ACTION_REOPEN_DRAWING = "reopen_drawing"
WORKFLOW_ACTION_COMPLETE_PLATE_LAYOUT = "complete_plate_layout"
WORKFLOW_ACTION_RESET_PLATE_LAYOUT = "reset_plate_layout"
WORKFLOW_ACTION_REOPEN_PLATE_LAYOUT = "reopen_plate_layout"

VALID_WORKFLOW_ACTIONS = frozenset(
    {
        WORKFLOW_ACTION_START_MODELING,
        WORKFLOW_ACTION_COMPLETE_MODELING,
        WORKFLOW_ACTION_RESET_MODELING,
        WORKFLOW_ACTION_REOPEN_MODELING,
        WORKFLOW_ACTION_START_PLATE_LAYOUT,
        WORKFLOW_ACTION_COMPLETE_DRAWING,
        WORKFLOW_ACTION_RESET_DRAWING,
        WORKFLOW_ACTION_REOPEN_DRAWING,
        WORKFLOW_ACTION_COMPLETE_PLATE_LAYOUT,
        WORKFLOW_ACTION_RESET_PLATE_LAYOUT,
        WORKFLOW_ACTION_REOPEN_PLATE_LAYOUT,
    }
)


def _now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def needs_detail_workflow(natures: list[str]) -> bool:
    return "detail" in natures or "plate_layout" in natures


def initial_plate_layout_status(natures: list[str]) -> str:
    if "plate_layout" in natures:
        return PHASE_STATUS_NOT_STARTED
    return PHASE_STATUS_NOT_APPLICABLE


def is_main_flow_completed(workflow: ProjectDetailWorkflow, has_plate_layout: bool) -> bool:
    if workflow.modeling_status != PHASE_STATUS_COMPLETED:
        return False
    if workflow.drawing_status != PHASE_STATUS_COMPLETED:
        return False
    if has_plate_layout and workflow.plate_layout_status != PHASE_STATUS_COMPLETED:
        return False
    return True


def map_detail_workflow(
    row: ProjectDetailWorkflow | None,
    *,
    updated_by_name: str = "",
) -> dict | None:
    if row is None:
        return None
    return {
        "modelingStatus": row.modeling_status,
        "drawingStatus": row.drawing_status,
        "plateLayoutStatus": row.plate_layout_status,
        "modelingStartedAt": (row.modeling_started_at or "").strip(),
        "modelingCompletedAt": (row.modeling_completed_at or "").strip(),
        "drawingStartedAt": (row.drawing_started_at or "").strip(),
        "drawingCompletedAt": (row.drawing_completed_at or "").strip(),
        "plateLayoutStartedAt": (row.plate_layout_started_at or "").strip(),
        "plateLayoutCompletedAt": (row.plate_layout_completed_at or "").strip(),
        "modelWeightTons": row.model_weight_tons,
        "modelWeightUpdatedAt": (row.model_weight_updated_at or "").strip(),
        "modelWeightUpdatedBy": (row.model_weight_updated_by or "").strip(),
        "modelWeightUpdatedByName": updated_by_name,
    }


def get_detail_workflow(project_no: str) -> ProjectDetailWorkflow | None:
    return ProjectDetailWorkflow.query.get(project_no)


def get_workflows_orm_map(project_nos: list[str]) -> dict[str, ProjectDetailWorkflow]:
    return _get_workflows_map(project_nos)


def _get_workflows_map(project_nos: list[str]) -> dict[str, ProjectDetailWorkflow]:
    if not project_nos:
        return {}
    rows = ProjectDetailWorkflow.query.filter(ProjectDetailWorkflow.project_no.in_(project_nos)).all()
    return {row.project_no: row for row in rows}


def get_detail_workflows_map(project_nos: list[str]) -> dict[str, dict | None]:
    workflows = _get_workflows_map(project_nos)
    return {project_no: map_detail_workflow(workflows.get(project_no)) for project_no in project_nos}


def ensure_detail_workflow(project_no: str, natures: list[str]) -> ProjectDetailWorkflow | None:
    if not needs_detail_workflow(natures):
        delete_detail_workflow(project_no)
        return None

    workflow = get_detail_workflow(project_no)
    plate_status = initial_plate_layout_status(natures)
    if workflow is None:
        workflow = ProjectDetailWorkflow(
            project_no=project_no,
            modeling_status=PHASE_STATUS_NOT_STARTED,
            drawing_status=PHASE_STATUS_NOT_STARTED,
            plate_layout_status=plate_status,
        )
        db.session.add(workflow)
        return workflow

    if "plate_layout" in natures:
        if workflow.plate_layout_status == PHASE_STATUS_NOT_APPLICABLE:
            workflow.plate_layout_status = PHASE_STATUS_NOT_STARTED
    else:
        workflow.plate_layout_status = PHASE_STATUS_NOT_APPLICABLE
        workflow.plate_layout_started_at = None
        workflow.plate_layout_completed_at = None

    workflow.updated_at = _now_text()
    return workflow


def delete_detail_workflow(project_no: str) -> None:
    workflow = get_detail_workflow(project_no)
    if workflow is not None:
        db.session.delete(workflow)


def resolve_detail_completed(
    natures: list[str],
    workflow: ProjectDetailWorkflow | None,
    *,
    manual_value: bool = False,
) -> bool:
    if not any(nature in {"detail", "detail_issue", "plate_layout", "tile_layout"} for nature in natures):
        return False
    if needs_detail_workflow(natures):
        if workflow is None:
            return False
        return is_main_flow_completed(workflow, "plate_layout" in natures)
    return manual_value


def _touch_started(workflow: ProjectDetailWorkflow, field: str, now: str) -> None:
    if not getattr(workflow, field):
        setattr(workflow, field, now)


def _reset_drawing_phase(workflow: ProjectDetailWorkflow) -> None:
    workflow.drawing_status = PHASE_STATUS_NOT_STARTED
    workflow.drawing_started_at = None
    workflow.drawing_completed_at = None


def _reset_plate_layout_phase(workflow: ProjectDetailWorkflow, *, has_plate_layout: bool) -> None:
    if not has_plate_layout:
        workflow.plate_layout_status = PHASE_STATUS_NOT_APPLICABLE
    else:
        workflow.plate_layout_status = PHASE_STATUS_NOT_STARTED
    workflow.plate_layout_started_at = None
    workflow.plate_layout_completed_at = None


def apply_workflow_action(project_no: str, action: str, natures: list[str]) -> tuple[ProjectDetailWorkflow | None, str | None]:
    normalized_action = (action or "").strip()
    if normalized_action not in VALID_WORKFLOW_ACTIONS:
        return None, "无效的细化流程操作"

    if not needs_detail_workflow(natures):
        return None, "当前项目不适用细化主流程"

    workflow = ensure_detail_workflow(project_no, natures)
    assert workflow is not None

    now = _now_text()
    has_plate_layout = "plate_layout" in natures

    if normalized_action == WORKFLOW_ACTION_START_MODELING:
        if workflow.modeling_status != PHASE_STATUS_NOT_STARTED:
            return None, "建模阶段已开始或已完成"
        workflow.modeling_status = PHASE_STATUS_IN_PROGRESS
        _touch_started(workflow, "modeling_started_at", now)

    elif normalized_action == WORKFLOW_ACTION_COMPLETE_MODELING:
        if workflow.modeling_status != PHASE_STATUS_IN_PROGRESS:
            return None, "建模尚未开始或已完成"
        workflow.modeling_status = PHASE_STATUS_COMPLETED
        workflow.modeling_completed_at = now
        if workflow.drawing_status == PHASE_STATUS_NOT_STARTED:
            workflow.drawing_status = PHASE_STATUS_IN_PROGRESS
            _touch_started(workflow, "drawing_started_at", now)

    elif normalized_action == WORKFLOW_ACTION_RESET_MODELING:
        if workflow.modeling_status != PHASE_STATUS_IN_PROGRESS:
            return None, "仅进行中的建模可撤回至未开始"
        workflow.modeling_status = PHASE_STATUS_NOT_STARTED
        workflow.modeling_started_at = None
        workflow.modeling_completed_at = None
        _reset_drawing_phase(workflow)
        _reset_plate_layout_phase(workflow, has_plate_layout=has_plate_layout)

    elif normalized_action == WORKFLOW_ACTION_REOPEN_MODELING:
        if workflow.modeling_status != PHASE_STATUS_COMPLETED:
            return None, "仅已完成的建模可重新打开"
        workflow.modeling_status = PHASE_STATUS_IN_PROGRESS
        workflow.modeling_completed_at = None
        _reset_drawing_phase(workflow)
        _reset_plate_layout_phase(workflow, has_plate_layout=has_plate_layout)

    elif normalized_action == WORKFLOW_ACTION_START_PLATE_LAYOUT:
        if not has_plate_layout:
            return None, "当前项目不需要排板"
        if workflow.modeling_status != PHASE_STATUS_COMPLETED:
            return None, "建模尚未完成，不能开始排板"
        if workflow.drawing_status not in {PHASE_STATUS_IN_PROGRESS, PHASE_STATUS_COMPLETED}:
            return None, "调图尚未开始，不能开始排板"
        if workflow.plate_layout_status != PHASE_STATUS_NOT_STARTED:
            return None, "排板已开始或已完成"
        workflow.plate_layout_status = PHASE_STATUS_IN_PROGRESS
        _touch_started(workflow, "plate_layout_started_at", now)

    elif normalized_action == WORKFLOW_ACTION_COMPLETE_DRAWING:
        if workflow.drawing_status != PHASE_STATUS_IN_PROGRESS:
            return None, "调图尚未开始或已完成"
        workflow.drawing_status = PHASE_STATUS_COMPLETED
        workflow.drawing_completed_at = now

    elif normalized_action == WORKFLOW_ACTION_RESET_DRAWING:
        if workflow.modeling_status != PHASE_STATUS_COMPLETED:
            return None, "建模尚未完成，不能撤回调图"
        if workflow.drawing_status != PHASE_STATUS_IN_PROGRESS:
            return None, "仅进行中的调图可撤回至未开始"
        _reset_drawing_phase(workflow)
        _reset_plate_layout_phase(workflow, has_plate_layout=has_plate_layout)

    elif normalized_action == WORKFLOW_ACTION_REOPEN_DRAWING:
        if workflow.drawing_status != PHASE_STATUS_COMPLETED:
            return None, "仅已完成的调图可重新打开"
        workflow.drawing_status = PHASE_STATUS_IN_PROGRESS
        workflow.drawing_completed_at = None
        _reset_plate_layout_phase(workflow, has_plate_layout=has_plate_layout)

    elif normalized_action == WORKFLOW_ACTION_COMPLETE_PLATE_LAYOUT:
        if workflow.plate_layout_status != PHASE_STATUS_IN_PROGRESS:
            return None, "排板尚未开始或已完成"
        workflow.plate_layout_status = PHASE_STATUS_COMPLETED
        workflow.plate_layout_completed_at = now

    elif normalized_action == WORKFLOW_ACTION_RESET_PLATE_LAYOUT:
        if not has_plate_layout:
            return None, "当前项目不需要排板"
        if workflow.plate_layout_status != PHASE_STATUS_IN_PROGRESS:
            return None, "仅进行中的排板可撤回至未开始"
        workflow.plate_layout_status = PHASE_STATUS_NOT_STARTED
        workflow.plate_layout_started_at = None
        workflow.plate_layout_completed_at = None

    elif normalized_action == WORKFLOW_ACTION_REOPEN_PLATE_LAYOUT:
        if not has_plate_layout:
            return None, "当前项目不需要排板"
        if workflow.plate_layout_status != PHASE_STATUS_COMPLETED:
            return None, "仅已完成的排板可重新打开"
        workflow.plate_layout_status = PHASE_STATUS_IN_PROGRESS
        workflow.plate_layout_completed_at = None

    workflow.updated_at = now
    return workflow, None


VALID_PHASE_STATUSES = frozenset(
    {PHASE_STATUS_NOT_STARTED, PHASE_STATUS_IN_PROGRESS, PHASE_STATUS_COMPLETED}
)
VALID_PLATE_LAYOUT_STATUSES = VALID_PHASE_STATUSES | {PHASE_STATUS_NOT_APPLICABLE}


def _normalize_workflow_datetime(value) -> str | None:
    text_value = (value or "").strip()
    return text_value or None


def _validate_phase_status(value: str | None, *, field_label: str) -> tuple[str | None, str | None]:
    normalized = (value or "").strip()
    if normalized not in VALID_PHASE_STATUSES:
        return None, f"{field_label}状态无效"
    return normalized, None


def _validate_plate_layout_status(value: str | None, *, has_plate_layout: bool) -> tuple[str | None, str | None]:
    normalized = (value or "").strip()
    if normalized not in VALID_PLATE_LAYOUT_STATUSES:
        return None, "排板状态无效"
    if not has_plate_layout and normalized != PHASE_STATUS_NOT_APPLICABLE:
        return None, "未勾选项目性质「排板」时，该阶段只能为不适用"
    if has_plate_layout and normalized == PHASE_STATUS_NOT_APPLICABLE:
        return None, "已勾选「排板」性质时，不能设为不适用"
    return normalized, None


def _apply_phase_fields(
    workflow: ProjectDetailWorkflow,
    *,
    status_field: str,
    started_field: str,
    completed_field: str,
    status: str,
    started_at: str | None,
    completed_at: str | None,
) -> None:
    setattr(workflow, status_field, status)
    setattr(workflow, started_field, started_at)
    setattr(workflow, completed_field, completed_at)


def update_detail_workflow(project_no: str, payload: dict, natures: list[str]) -> tuple[ProjectDetailWorkflow | None, str | None]:
    if not needs_detail_workflow(natures):
        return None, "当前项目不适用细化主流程"

    workflow = ensure_detail_workflow(project_no, natures)
    assert workflow is not None

    has_plate_layout = "plate_layout" in natures

    modeling_status, error = _validate_phase_status(payload.get("modelingStatus"), field_label="建模")
    if error:
        return None, error
    drawing_status, error = _validate_phase_status(payload.get("drawingStatus"), field_label="调图")
    if error:
        return None, error
    plate_layout_status, error = _validate_plate_layout_status(
        payload.get("plateLayoutStatus"),
        has_plate_layout=has_plate_layout,
    )
    if error:
        return None, error

    modeling_started_at = _normalize_workflow_datetime(payload.get("modelingStartedAt"))
    modeling_completed_at = _normalize_workflow_datetime(payload.get("modelingCompletedAt"))
    drawing_started_at = _normalize_workflow_datetime(payload.get("drawingStartedAt"))
    drawing_completed_at = _normalize_workflow_datetime(payload.get("drawingCompletedAt"))
    plate_layout_started_at = _normalize_workflow_datetime(payload.get("plateLayoutStartedAt"))
    plate_layout_completed_at = _normalize_workflow_datetime(payload.get("plateLayoutCompletedAt"))

    if modeling_status == PHASE_STATUS_NOT_STARTED:
        modeling_started_at = None
        modeling_completed_at = None
    elif modeling_status == PHASE_STATUS_IN_PROGRESS:
        modeling_completed_at = None

    if drawing_status == PHASE_STATUS_NOT_STARTED:
        drawing_started_at = None
        drawing_completed_at = None
    elif drawing_status == PHASE_STATUS_IN_PROGRESS:
        drawing_completed_at = None

    if plate_layout_status in {PHASE_STATUS_NOT_APPLICABLE, PHASE_STATUS_NOT_STARTED}:
        plate_layout_started_at = None
        plate_layout_completed_at = None
    elif plate_layout_status == PHASE_STATUS_IN_PROGRESS:
        plate_layout_completed_at = None

    if modeling_status == PHASE_STATUS_COMPLETED and not modeling_completed_at and modeling_started_at:
        modeling_completed_at = modeling_started_at

    if drawing_status == PHASE_STATUS_COMPLETED and not drawing_completed_at and drawing_started_at:
        drawing_completed_at = drawing_started_at

    if (
        plate_layout_status == PHASE_STATUS_COMPLETED
        and not plate_layout_completed_at
        and plate_layout_started_at
    ):
        plate_layout_completed_at = plate_layout_started_at

    _apply_phase_fields(
        workflow,
        status_field="modeling_status",
        started_field="modeling_started_at",
        completed_field="modeling_completed_at",
        status=modeling_status,
        started_at=modeling_started_at,
        completed_at=modeling_completed_at,
    )
    _apply_phase_fields(
        workflow,
        status_field="drawing_status",
        started_field="drawing_started_at",
        completed_field="drawing_completed_at",
        status=drawing_status,
        started_at=drawing_started_at,
        completed_at=drawing_completed_at,
    )
    _apply_phase_fields(
        workflow,
        status_field="plate_layout_status",
        started_field="plate_layout_started_at",
        completed_field="plate_layout_completed_at",
        status=plate_layout_status,
        started_at=plate_layout_started_at,
        completed_at=plate_layout_completed_at,
    )

    workflow.updated_at = _now_text()
    return workflow, None


def _get_jwt_personnel_id() -> str | None:
    try:
        claims = get_jwt()
    except RuntimeError:
        return None
    personnel_id = (claims.get("personnel_id") or "").strip()
    return personnel_id or None


def _normalize_model_weight_tons(value) -> tuple[float | None, str | None]:
    if value is None or value == "":
        return None, None
    try:
        weight = float(value)
    except (TypeError, ValueError):
        return None, "模型重量格式无效"
    if weight < 0:
        return None, "模型重量不能为负数"
    return round(weight, 3), None


def _touch_model_weight_audit(workflow: ProjectDetailWorkflow, updated_by: str | None) -> None:
    workflow.model_weight_updated_at = _now_text()
    workflow.model_weight_updated_by = updated_by


def update_model_weight(
    project_no: str,
    model_weight_tons,
    natures: list[str],
    *,
    updated_by: str | None = None,
) -> tuple[ProjectDetailWorkflow | None, str | None]:
    if not needs_detail_workflow(natures):
        return None, "当前项目不适用细化主流程"

    weight, error = _normalize_model_weight_tons(model_weight_tons)
    if error:
        return None, error

    workflow = ensure_detail_workflow(project_no, natures)
    assert workflow is not None

    previous = workflow.model_weight_tons
    if previous == weight:
        return workflow, None

    workflow.model_weight_tons = weight
    _touch_model_weight_audit(workflow, updated_by)
    workflow.updated_at = _now_text()
    return workflow, None


def update_model_weight_from_request(
    project_no: str,
    payload: dict,
    natures: list[str],
) -> tuple[ProjectDetailWorkflow | None, str | None]:
    return update_model_weight(
        project_no,
        payload.get("modelWeightTons"),
        natures,
        updated_by=_get_jwt_personnel_id(),
    )
