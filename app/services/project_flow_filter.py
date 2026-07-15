"""项目性质与流程状态列过滤（与前端 ProjectForm / MyProjectForm 逻辑对齐）。"""

from __future__ import annotations

VALID_FLOW_FILTER_KINDS = frozenset({"process", "design", "detail", "detailMain"})
VALID_NATURE_FILTER_VALUES = frozenset(
    {"design", "detail", "detail_issue", "plate_layout", "floor_deck_layout", "tile_layout"}
)
VALID_PROGRESS_PHASES = frozenset({"not_started", "in_progress", "completed"})
VALID_DETAIL_MAIN_PHASES = frozenset(
    {
        "pending_modeling",
        "modeling",
        "drawing",
        "drawing_plate_layout",
        "drawing_finishing",
        "plate_layout_finishing",
        "detail_completed",
    }
)
DESIGN_TEAM = "设计组"
DETAIL_TEAM = "细化组"

_DETAIL_MAIN_PHASE_EXPR = """CASE
  WHEN w.modeling_status != 'completed'
    OR w.drawing_status != 'completed'
    OR (
      COALESCE(w.plate_layout_enabled, 1) != 0
      AND w.plate_layout_status != 'completed'
    )
  THEN CASE
    WHEN w.modeling_status != 'completed' THEN
      CASE WHEN w.modeling_status = 'in_progress' THEN 'modeling' ELSE 'pending_modeling' END
    WHEN COALESCE(w.plate_layout_enabled, 1) != 0
      AND w.drawing_status = 'in_progress'
      AND w.plate_layout_status = 'in_progress'
    THEN 'drawing_plate_layout'
    WHEN COALESCE(w.plate_layout_enabled, 1) != 0
      AND w.drawing_status = 'completed'
      AND w.plate_layout_status = 'in_progress'
    THEN 'plate_layout_finishing'
    WHEN COALESCE(w.plate_layout_enabled, 1) != 0
      AND w.drawing_status = 'in_progress'
      AND w.plate_layout_status = 'completed'
    THEN 'drawing_finishing'
    ELSE 'drawing'
  END
  ELSE 'detail_completed'
END"""


def parse_flow_filters(raw: str) -> list[str]:
    return list(
        dict.fromkeys(
            item.strip()
            for item in (raw or "").split(",")
            if item.strip()
        )
    )


def parse_nature_filters(raw: str) -> list[str]:
    unique = list(
        dict.fromkeys(
            item.strip()
            for item in (raw or "").split(",")
            if item and item.strip()
        )
    )
    return [item for item in unique if item in VALID_NATURE_FILTER_VALUES]


def parse_exclude_project_nos(raw: str) -> list[str]:
    return list(
        dict.fromkeys(
            item.strip()
            for item in (raw or "").split(",")
            if item and item.strip()
        )
    )


def _parse_flow_filter(value: str) -> tuple[str, str] | None:
    separator_index = value.find(":")
    if separator_index <= 0:
        return None
    kind = value[:separator_index]
    phase = value[separator_index + 1 :]
    if not phase or kind not in VALID_FLOW_FILTER_KINDS:
        return None
    return kind, phase


def _has_design_nature_sql() -> str:
    return """EXISTS (
      SELECT 1 FROM project_natures pn
      WHERE pn.project_no = p.project_no AND pn.nature = 'design'
    )"""


def _has_detail_group_nature_sql() -> str:
    return """EXISTS (
      SELECT 1 FROM project_natures pn
      WHERE pn.project_no = p.project_no
        AND pn.nature IN ('detail', 'detail_issue', 'floor_deck_layout', 'tile_layout')
    )"""


def _uses_detail_workflow_sql() -> str:
    return """(
      EXISTS (
        SELECT 1 FROM project_natures pn
        WHERE pn.project_no = p.project_no AND pn.nature = 'detail'
      )
      AND EXISTS (
        SELECT 1 FROM project_detail_workflows w
        WHERE w.project_no = p.project_no
      )
    )"""


def _design_started_sql() -> str:
    return """(
      EXISTS (
        SELECT 1 FROM project_personnel pp
        INNER JOIN personnel per ON per.id = pp.personnel_id
        WHERE pp.project_no = p.project_no AND per.team = :design_team
      )
      OR TRIM(IFNULL(p.design_work_path, '')) != ''
    )"""


def _detail_started_sql() -> str:
    return """(
      EXISTS (
        SELECT 1 FROM project_personnel pp
        INNER JOIN personnel per ON per.id = pp.personnel_id
        WHERE pp.project_no = p.project_no AND per.team = :detail_team
      )
      OR TRIM(IFNULL(p.detail_work_path, '')) != ''
    )"""


def _design_phase_sql(phase: str) -> str | None:
    if phase not in VALID_PROGRESS_PHASES:
        return None
    if phase == "completed":
        return f"({_has_design_nature_sql()} AND p.design_completed = 1)"
    if phase == "in_progress":
        return (
            f"({_has_design_nature_sql()} AND p.design_completed = 0 AND {_design_started_sql()})"
        )
    return (
        f"({_has_design_nature_sql()} AND p.design_completed = 0 "
        f"AND NOT ({_design_started_sql()}))"
    )


def _detail_simple_phase_sql(phase: str) -> str | None:
    if phase not in VALID_PROGRESS_PHASES:
        return None
    base = f"({_has_detail_group_nature_sql()} AND NOT ({_uses_detail_workflow_sql()}))"
    if phase == "completed":
        return f"({base} AND p.detail_completed = 1)"
    if phase == "in_progress":
        return f"({base} AND p.detail_completed = 0 AND {_detail_started_sql()})"
    return f"({base} AND p.detail_completed = 0 AND NOT ({_detail_started_sql()}))"


def _detail_main_phase_sql(param_name: str) -> str:
    return f"""EXISTS (
      SELECT 1
      FROM project_detail_workflows w
      INNER JOIN project_natures pn
        ON pn.project_no = p.project_no AND pn.nature = 'detail'
      WHERE w.project_no = p.project_no
        AND ({_DETAIL_MAIN_PHASE_EXPR}) = :{param_name}
    )"""


def _flow_filter_sql(
    filter_value: str,
    *,
    personnel_team: str = "",
) -> str | None:
    parsed = _parse_flow_filter(filter_value)
    if not parsed:
        return None

    kind, value = parsed

    if kind == "process":
        return "p.status = :process_status"

    if kind == "design":
        if personnel_team and personnel_team != DESIGN_TEAM:
            return "0"
        return _design_phase_sql(value)

    if kind == "detail":
        if personnel_team and personnel_team != DETAIL_TEAM:
            return "0"
        return _detail_simple_phase_sql(value)

    if kind == "detailMain":
        if personnel_team and personnel_team != DETAIL_TEAM:
            return "0"
        if value not in VALID_DETAIL_MAIN_PHASES:
            return None
        return "__detail_main__"

    return None


def build_flow_filter_clause(
    flow_filters: list[str] | None,
    *,
    personnel_team: str = "",
) -> tuple[str, dict]:
    if not flow_filters:
        return "", {}

    clauses: list[str] = []
    params: dict = {
        "design_team": DESIGN_TEAM,
        "detail_team": DETAIL_TEAM,
    }

    for index, filter_value in enumerate(flow_filters):
        parsed = _parse_flow_filter(filter_value)
        if not parsed:
            continue

        kind, value = parsed

        if kind == "process":
            param_name = f"process_status_{index}"
            params[param_name] = value
            clauses.append(f"p.status = :{param_name}")
            continue

        if kind == "detailMain":
            if personnel_team and personnel_team != DETAIL_TEAM:
                continue
            if value not in VALID_DETAIL_MAIN_PHASES:
                continue
            param_name = f"detail_main_phase_{index}"
            params[param_name] = value
            clauses.append(_detail_main_phase_sql(param_name))
            continue

        clause = _flow_filter_sql(filter_value, personnel_team=personnel_team)
        if clause and clause != "0":
            clauses.append(clause)

    if not clauses:
        return "", params

    return f"({' OR '.join(clauses)})", params


def build_nature_filter_clause(nature_filters: list[str] | None) -> tuple[str, dict]:
    if not nature_filters:
        return "", {}

    placeholders = ", ".join(f":nature_{index}" for index, _ in enumerate(nature_filters))
    params = {f"nature_{index}": value for index, value in enumerate(nature_filters)}
    clause = f"""EXISTS (
      SELECT 1 FROM project_natures pn
      WHERE pn.project_no = p.project_no AND pn.nature IN ({placeholders})
    )"""
    return clause, params


def build_exclude_project_nos_clause(exclude_project_nos: list[str] | None) -> tuple[str, dict]:
    if not exclude_project_nos:
        return "", {}

    placeholders = ", ".join(f":exclude_no_{index}" for index, _ in enumerate(exclude_project_nos))
    params = {f"exclude_no_{index}": value for index, value in enumerate(exclude_project_nos)}
    return f"p.project_no NOT IN ({placeholders})", params
