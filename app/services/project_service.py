from __future__ import annotations

import re
from datetime import datetime

from sqlalchemy import and_, func, select, text

from steeltech_db.extensions import db
from steeltech_db.models import Personnel, Project, ProjectDetailWorkflow, ProjectDesignWorkflow, ProjectNature
from steeltech_db.project_split import (
    has_hyphen_split_suffix,
    is_split_project_no,
    parse_base_project_no,
    parse_hyphen_root,
)
from steeltech_db.project_status import (
    PROJECT_STATUS_ACTIVE,
    PROJECT_STATUS_DONE,
    PROJECT_STATUS_LABELS,
    VALID_PROJECT_STATUSES,
)
from app.services import design_workflow_service, detail_workflow_service, project_flow_filter, tag_service
from app.utils.pagination import ListPageQuery, compute_paginated_window
from app.utils.paths import normalize_relative_path
from app.utils.sql_helpers import insert_ignore, now_expr
from app.utils.sql_mapper import mapper

VALID_NATURES = frozenset(
    {"design", "detail", "detail_issue", "plate_layout", "floor_deck_layout", "tile_layout"}
)
DETAIL_GROUP_NATURES = frozenset({"detail", "detail_issue", "floor_deck_layout", "tile_layout"})
JIAGONGDAN_CONTENT_PATTERN = r"(?:^|\n)项目分类[：:]\s*.*加工单"
JIAGONGDAN_CONTACT_ID_PATTERN = re.compile(r"^(?:加工单-|BRD\d{6}C\d{9}$)", re.IGNORECASE)


def _is_jiagongdan_contact_id(contact_id: str) -> bool:
    return bool(JIAGONGDAN_CONTACT_ID_PATTERN.match((contact_id or "").strip()))

PROJECT_RECEIVED_DATE_SQL = """COALESCE(
    NULLIF(TRIM(p.derived_received_date), ''),
    NULLIF(TRIM(p.planned_start_date), ''),
    ''
)"""
PROJECT_LIST_ORDER = f"{PROJECT_RECEIVED_DATE_SQL} DESC, p.project_no DESC"


def recompute_derived_received_date(project_no: str) -> None:
    """重新计算项目的 derived_received_date（received_date 或最早联系单日期）。"""
    project = Project.query.get(project_no)
    if project is None:
        return
    received = (project.received_date or "").strip()
    if received:
        project.derived_received_date = received
    else:
        contact_date = get_received_date_from_contacts(project_no)
        project.derived_received_date = contact_date if contact_date else project.planned_start_date or ""
    db.session.commit()


def resolve_project_no(project_no: str) -> str:
    """业务项目号：去除历史拆分后缀，多联系单通过关联表挂载。"""
    return parse_base_project_no((project_no or "").strip())


def _build_contact_links(project_no: str, contact_form_ids: list[str]) -> list[dict]:
    return [{"projectNo": project_no, "contactFormId": contact_id} for contact_id in contact_form_ids]


def normalize_project_status(value: str | None, *, default: str = "active") -> tuple[str | None, str | None]:
    status = (value or "").strip() or default
    if status not in VALID_PROJECT_STATUSES:
        labels = "、".join(PROJECT_STATUS_LABELS[code] for code in sorted(VALID_PROJECT_STATUSES))
        return None, f"项目状态无效，仅支持：{labels}"
    return status, None


def normalize_completion_flag(value, *, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        return normalized in {"1", "true", "yes", "y", "on"}
    return bool(value)


def normalize_drawing_issue_year_month(value, *, default: str = "") -> tuple[str, str | None]:
    if value is None:
        return default, None
    normalized = str(value).strip()
    if not normalized:
        return "", None
    if len(normalized) == 7 and normalized[4] == "-":
        year_part, month_part = normalized.split("-", 1)
        if year_part.isdigit() and month_part.isdigit():
            month = int(month_part)
            if 1 <= month <= 12:
                return f"{int(year_part):04d}-{month:02d}", None
    return default, "发图年月格式无效，应为 YYYY-MM"


def _row_to_dict(row) -> dict:
    if hasattr(row, "_mapping"):
        return dict(row._mapping)
    return {c.name: getattr(row, c.name) for c in row.__table__.columns}


def get_contact_form_ids(project_no: str) -> list[str]:
    rows = mapper("project").all("get_contact_form_ids", project_no=project_no)
    return [(row.contact_form_id or "").strip() for row in rows if row.contact_form_id]


def get_project_is_jiagongdan(project_no: str) -> bool:
    rows = db.session.execute(
        text(
            """
            SELECT cf.id, cf.title, cf.content
            FROM contact_form_projects cfp
            INNER JOIN contact_forms cf ON cf.id = cfp.contact_form_id
            WHERE cfp.project_no = :project_no
            ORDER BY cf.id
            """
        ),
        {"project_no": project_no},
    ).all()
    for row in rows:
        contact_id = (row.id or "").strip()
        title = (row.title or "").strip()
        content = (row.content or "").strip()
        if _is_jiagongdan_contact_id(contact_id):
            return True
        if "加工单" in title:
            return True
        if re.search(JIAGONGDAN_CONTENT_PATTERN, content):
            return True
    return False


def get_project_natures(project_no: str) -> list[str]:
    rows = (
        ProjectNature.query.filter_by(project_no=project_no)
        .order_by(ProjectNature.nature)
        .all()
    )
    return [row.nature for row in rows if row.nature in VALID_NATURES]


def get_received_date_from_contacts(project_no: str) -> str:
    row = db.session.execute(
        text(
            """
            SELECT MIN(cf.received_date) AS received_date
            FROM contact_form_projects cfp
            INNER JOIN contact_forms cf ON cf.id = cfp.contact_form_id
            WHERE cfp.project_no = :project_no
            """
        ),
        {"project_no": project_no},
    ).first()
    return (row.received_date or "").strip() if row else ""


def get_assigned_personnel(project_no: str) -> list[dict]:
    rows = db.session.execute(
        text(
            """
            SELECT p.id, p.name, p.team
            FROM project_personnel pp
            INNER JOIN personnel p ON p.id = pp.personnel_id
            WHERE pp.project_no = :project_no
            ORDER BY p.team, p.name
            """
        ),
        {"project_no": project_no},
    ).all()
    return [{"id": row.id, "name": row.name, "team": row.team} for row in rows]


def map_project_dates(row: dict) -> dict:
    return {
        "plannedStartDate": (row.get("planned_start_date") or row.get("start_date") or "").strip(),
        "plannedEndDate": (row.get("planned_end_date") or row.get("end_date") or "").strip(),
        "actualStartDate": (row.get("actual_start_date") or "").strip(),
        "actualEndDate": (row.get("actual_end_date") or "").strip(),
    }


def resolve_received_date(row: dict) -> str:
    stored = (row.get("received_date") or "").strip()
    if stored:
        return stored
    from_contacts = get_received_date_from_contacts(row["project_no"])
    if from_contacts:
        return from_contacts
    dates = map_project_dates(row)
    return dates["plannedStartDate"]


def _get_personnel_names_by_ids(personnel_ids: list[str]) -> dict[str, str]:
    unique_ids = list(dict.fromkeys(item for item in personnel_ids if item))
    if not unique_ids:
        return {}
    placeholders = ", ".join(f":p{i}" for i in range(len(unique_ids)))
    params = {f"p{i}": value for i, value in enumerate(unique_ids)}
    rows = db.session.execute(
        text(f"SELECT id, name FROM personnel WHERE id IN ({placeholders})"),
        params,
    ).all()
    return {row.id: row.name for row in rows}


def _map_detail_workflow_with_audit(row: ProjectDetailWorkflow | None) -> dict | None:
    if row is None:
        return None
    updated_by_name = ""
    if row.model_weight_updated_by:
        names = _get_personnel_names_by_ids([row.model_weight_updated_by])
        updated_by_name = names.get(row.model_weight_updated_by, "")
    return detail_workflow_service.map_detail_workflow(row, updated_by_name=updated_by_name)


def map_project(row: dict) -> dict:
    project_no = row["project_no"]
    contact_form_ids = get_contact_form_ids(project_no)
    assigned = get_assigned_personnel(project_no)
    dates = map_project_dates(row)
    is_jiagongdan = get_project_is_jiagongdan(project_no)
    design_work_path = normalize_relative_path(row.get("design_work_path") or "")
    detail_work_path = normalize_relative_path(row.get("detail_work_path") or "")
    legacy_local = normalize_relative_path(row.get("local_work_path") or "")
    return {
        "projectNo": project_no,
        "baseProjectNo": project_no,
        "name": row["name"],
        "customer": row.get("customer") or "",
        "isJiagongdan": is_jiagongdan,
        "status": row["status"],
        "designCompleted": normalize_completion_flag(row.get("design_completed")),
        "detailCompleted": normalize_completion_flag(row.get("detail_completed")),
        "tileLayoutCompleted": normalize_completion_flag(row.get("tile_layout_completed")),
        "floorDeckLayoutCompleted": normalize_completion_flag(row.get("floor_deck_layout_completed")),
        "drawingIssueEnabled": normalize_completion_flag(row.get("drawing_issue_enabled")),
        "drawingIssueYearMonth": (row.get("drawing_issue_year_month") or "").strip(),
        "natures": get_project_natures(project_no),
        "tags": tag_service.get_project_tags(project_no),
        "assignedPersonnelIds": [item["id"] for item in assigned],
        "assignedPersonnel": assigned,
        "receivedDate": resolve_received_date(row),
        **dates,
        "designWorkPath": design_work_path,
        "detailWorkPath": detail_work_path,
        "localWorkPath": detail_work_path or design_work_path or legacy_local,
        "contactFormIds": contact_form_ids,
        "relatedProjects": _build_contact_links(project_no, contact_form_ids),
        "detailWorkflow": _map_detail_workflow_with_audit(
            detail_workflow_service.get_detail_workflow(project_no)
        ),
        "designWorkflow": design_workflow_service.map_design_workflow(
            design_workflow_service.get_design_workflow(project_no)
        ),
    }


def _get_natures_map(project_nos: list[str]) -> dict[str, list[str]]:
    if not project_nos:
        return {}
    placeholders = ", ".join(f":p{i}" for i in range(len(project_nos)))
    params = {f"p{i}": value for i, value in enumerate(project_nos)}
    rows = db.session.execute(
        text(
            f"""
            SELECT project_no, nature FROM project_natures
            WHERE project_no IN ({placeholders})
            ORDER BY nature
            """
        ),
        params,
    ).all()
    result: dict[str, list[str]] = {}
    for row in rows:
        if row.nature not in VALID_NATURES:
            continue
        result.setdefault(row.project_no, []).append(row.nature)
    return result


def _get_personnel_map(project_nos: list[str]) -> dict[str, list[dict]]:
    if not project_nos:
        return {}
    placeholders = ", ".join(f":p{i}" for i in range(len(project_nos)))
    params = {f"p{i}": value for i, value in enumerate(project_nos)}
    rows = db.session.execute(
        text(
            f"""
            SELECT pp.project_no, p.id, p.name, p.team
            FROM project_personnel pp
            INNER JOIN personnel p ON p.id = pp.personnel_id
            WHERE pp.project_no IN ({placeholders})
            ORDER BY pp.project_no, p.team, p.name
            """
        ),
        params,
    ).all()
    result: dict[str, list[dict]] = {}
    for row in rows:
        result.setdefault(row.project_no, []).append(
            {"id": row.id, "name": row.name, "team": row.team}
        )
    return result


def _get_contact_info_map(project_nos: list[str]) -> tuple[dict[str, list[str]], dict[str, bool]]:
    """一次查询返回 contact_ids 和 jiagongdan 两个 map（合并同表 JOIN）。"""
    if not project_nos:
        return {}, {}
    placeholders = ", ".join(f":p{i}" for i in range(len(project_nos)))
    params = {f"p{i}": value for i, value in enumerate(project_nos)}
    rows = db.session.execute(
        text(
            f"""
            SELECT cfp.project_no, cfp.contact_form_id, cf.id, cf.title, cf.content
            FROM contact_form_projects cfp
            INNER JOIN contact_forms cf ON cf.id = cfp.contact_form_id
            WHERE cfp.project_no IN ({placeholders})
            ORDER BY cfp.project_no, cfp.contact_form_id
            """
        ),
        params,
    ).all()
    contact_map: dict[str, list[str]] = {}
    jiagongdan_seen: set[str] = set()
    jiagongdan_map: dict[str, bool] = {}
    for row in rows:
        pno = row.project_no
        cid = (row.contact_form_id or "").strip()
        contact_map.setdefault(pno, []).append(cid)
        if pno not in jiagongdan_seen:
            cid_full = (row.id or "").strip()
            title = (row.title or "").strip()
            content = (row.content or "").strip()
            if (
                _is_jiagongdan_contact_id(cid_full)
                or "加工单" in title
                or re.search(JIAGONGDAN_CONTENT_PATTERN, content)
            ):
                jiagongdan_map[pno] = True
                jiagongdan_seen.add(pno)
    return contact_map, jiagongdan_map


def map_projects_batch(rows: list[dict]) -> list[dict]:
    project_nos = [row["project_no"] for row in rows]
    natures_map = _get_natures_map(project_nos)
    tags_map = tag_service.get_project_tags_map(project_nos)
    personnel_map = _get_personnel_map(project_nos)
    contact_map, jiagongdan_map = _get_contact_info_map(project_nos)
    workflows_map = detail_workflow_service.get_workflows_orm_map(project_nos)
    design_workflows_map = design_workflow_service.get_workflows_orm_map(project_nos)
    model_weight_updated_by_ids = [
        workflow.model_weight_updated_by
        for workflow in workflows_map.values()
        if workflow and workflow.model_weight_updated_by
    ]
    model_weight_updater_names = _get_personnel_names_by_ids(model_weight_updated_by_ids)
    result = []
    for row in rows:
        assigned = personnel_map.get(row["project_no"], [])
        dates = map_project_dates(row)
        design_work_path = normalize_relative_path(row.get("design_work_path") or "")
        detail_work_path = normalize_relative_path(row.get("detail_work_path") or "")
        legacy_local = normalize_relative_path(row.get("local_work_path") or "")
        project_no = row["project_no"]
        contact_form_ids = contact_map.get(project_no, [])
        result.append(
            {
                "projectNo": project_no,
                "baseProjectNo": project_no,
                "name": row["name"],
                "customer": row.get("customer") or "",
                "isJiagongdan": jiagongdan_map.get(row["project_no"], False),
                "status": row["status"],
                "designCompleted": normalize_completion_flag(row.get("design_completed")),
                "detailCompleted": normalize_completion_flag(row.get("detail_completed")),
                "tileLayoutCompleted": normalize_completion_flag(row.get("tile_layout_completed")),
                "floorDeckLayoutCompleted": normalize_completion_flag(row.get("floor_deck_layout_completed")),
                "drawingIssueEnabled": normalize_completion_flag(row.get("drawing_issue_enabled")),
                "drawingIssueYearMonth": (row.get("drawing_issue_year_month") or "").strip(),
                "natures": natures_map.get(row["project_no"], []),
                "tags": tags_map.get(row["project_no"], []),
                "assignedPersonnelIds": [item["id"] for item in assigned],
                "assignedPersonnel": assigned,
                "receivedDate": resolve_received_date(row),
                **dates,
                "designWorkPath": design_work_path,
                "detailWorkPath": detail_work_path,
                "localWorkPath": detail_work_path or design_work_path or legacy_local,
                "contactFormIds": contact_form_ids,
                "relatedProjects": _build_contact_links(project_no, contact_form_ids),
                "detailWorkflow": detail_workflow_service.map_detail_workflow(
                    workflows_map.get(project_no),
                    updated_by_name=model_weight_updater_names.get(
                        workflows_map[project_no].model_weight_updated_by, ""
                    )
                    if workflows_map.get(project_no) and workflows_map[project_no].model_weight_updated_by
                    else "",
                ),
                "designWorkflow": design_workflow_service.map_design_workflow(
                    design_workflows_map.get(project_no)
                ),
            }
        )
    return result


def _build_project_conditions(
    keyword: str,
    status: str,
    assigned_personnel_id: str = "",
    tag_ids: list[str] | None = None,
    *,
    nature_filters: list[str] | None = None,
    flow_filters: list[str] | None = None,
    personnel_team: str = "",
    exclude_project_nos: list[str] | None = None,
) -> tuple[list[str], dict]:
    """构建项目查询过滤条件（SQL 片段 + 参数），供 Core select 和 CTE rank 共用。"""
    conditions: list[str] = []
    params: dict = {}

    personnel_id = (assigned_personnel_id or "").strip()
    if personnel_id == "__unassigned__":
        conditions.append(
            """NOT EXISTS (
              SELECT 1 FROM project_personnel pp
              WHERE pp.project_no = p.project_no
            )"""
        )
    elif personnel_id:
        conditions.append(
            """EXISTS (
              SELECT 1 FROM project_personnel pp
              WHERE pp.project_no = p.project_no AND pp.personnel_id = :assigned_personnel_id
            )"""
        )
        params["assigned_personnel_id"] = personnel_id

    tag_clause, tag_params = tag_service.build_tag_exists_clause(
        entity_id_column="p.project_no",
        join_table="project_tags",
        join_entity_column="project_no",
        tag_ids=tag_ids or [],
    )
    if tag_clause:
        conditions.append(tag_clause)
        params.update(tag_params)

    if status:
        conditions.append("p.status = :status")
        params["status"] = status

    nature_clause, nature_params = project_flow_filter.build_nature_filter_clause(nature_filters)
    if nature_clause:
        conditions.append(nature_clause)
        params.update(nature_params)

    flow_clause, flow_params = project_flow_filter.build_flow_filter_clause(
        flow_filters,
        personnel_team=personnel_team,
    )
    if flow_clause:
        conditions.append(flow_clause)
        params.update(flow_params)

    exclude_clause, exclude_params = project_flow_filter.build_exclude_project_nos_clause(
        exclude_project_nos,
    )
    if exclude_clause:
        conditions.append(exclude_clause)
        params.update(exclude_params)

    if keyword:
        conditions.append(
            """(
              LOWER(p.project_no) LIKE :kw
              OR LOWER(p.name) LIKE :kw
              OR LOWER(IFNULL(p.customer, '')) LIKE :kw
              OR LOWER(IFNULL(p.received_date, '')) LIKE :kw
              OR LOWER(IFNULL(p.planned_start_date, '')) LIKE :kw
              OR LOWER(IFNULL(p.planned_end_date, '')) LIKE :kw
              OR LOWER(IFNULL(p.actual_start_date, '')) LIKE :kw
              OR LOWER(IFNULL(p.actual_end_date, '')) LIKE :kw
              OR LOWER(IFNULL(p.local_work_path, '')) LIKE :kw
              OR EXISTS (
                SELECT 1 FROM contact_form_projects cfp
                INNER JOIN contact_forms cf ON cf.id = cfp.contact_form_id AND cf.deleted_at IS NULL
                WHERE cfp.project_no = p.project_no AND LOWER(cfp.contact_form_id) LIKE :kw
              )
              OR EXISTS (
                SELECT 1 FROM project_personnel pp
                INNER JOIN personnel per ON per.id = pp.personnel_id
                WHERE pp.project_no = p.project_no
                  AND (LOWER(per.name) LIKE :kw OR LOWER(per.team) LIKE :kw)
              )
              OR EXISTS (
                SELECT 1 FROM project_natures pn
                WHERE pn.project_no = p.project_no
                  AND (
                    LOWER(pn.nature) LIKE :kw
                    OR (:raw_kw LIKE '%设计%' AND pn.nature = 'design')
                    OR (:raw_kw LIKE '%细化问题%' AND pn.nature = 'detail_issue')
                    OR (:raw_kw LIKE '%细化%' AND pn.nature = 'detail')
                    OR (
                      :raw_kw LIKE '%排板%'
                      AND EXISTS (
                        SELECT 1 FROM project_detail_workflows w
                        WHERE w.project_no = p.project_no AND w.plate_layout_enabled = 1
                      )
                    )
                    OR (:raw_kw LIKE '%排瓦%' AND pn.nature = 'tile_layout')
                    OR (
                      (
                        :raw_kw LIKE '%排楼板%'
                        OR :raw_kw LIKE '%楼层板%'
                        OR :raw_kw LIKE '%楼承板%'
                      )
                      AND pn.nature = 'floor_deck_layout'
                    )
                  )
              )
              OR EXISTS (
                SELECT 1 FROM project_tags pt
                INNER JOIN tags t ON t.id = pt.tag_id
                WHERE pt.project_no = p.project_no AND LOWER(t.name) LIKE :kw
              )
            )"""
        )
        params["kw"] = f"%{keyword}%"
        params["raw_kw"] = keyword

    return conditions, params


def get_project_rank(where_clause: str, params: dict, project_no: str) -> int | None:
    """获取项目在当前筛选条件下的排名（CTE 窗口函数）。"""
    row = db.session.execute(
        text(
            f"""
            WITH ranked AS (
              SELECT p.project_no, ROW_NUMBER() OVER (ORDER BY {PROJECT_LIST_ORDER}) - 1 AS `rank`
              FROM projects p
              {where_clause}
            )
            SELECT `rank` FROM ranked WHERE project_no = :project_no
            """
        ),
        {**params, "project_no": project_no},
    ).first()
    return int(row.rank) if row else None


def resolve_project_anchor(project_no: str) -> str:
    return resolve_project_no(project_no)


def normalize_natures(natures: list[str] | None) -> tuple[list[str] | None, str | None]:
    unique = list(dict.fromkeys(item.strip() for item in (natures or []) if item and item.strip()))
    invalid = [item for item in unique if item not in VALID_NATURES]
    if invalid:
        return None, "项目性质无效"
    return unique, None


def normalize_assigned_personnel_ids(ids: list[str] | None) -> tuple[list[str] | None, str | None]:
    unique = list(dict.fromkeys(item.strip() for item in (ids or []) if item and item.strip()))
    for personnel_id in unique:
        if Personnel.query.get(personnel_id) is None:
            return None, "分配人员不存在"
    return unique, None


def build_completion_flags(
    payload: dict,
    natures: list[str],
    existing: dict | None = None,
    workflow: ProjectDetailWorkflow | None = None,
) -> tuple[bool, bool]:
    design_completed = normalize_completion_flag(
        payload.get("designCompleted"),
        default=normalize_completion_flag((existing or {}).get("design_completed")),
    )
    manual_detail_completed = normalize_completion_flag(
        payload.get("detailCompleted"),
        default=normalize_completion_flag((existing or {}).get("detail_completed")),
    )
    if "design" not in natures:
        design_completed = False
    detail_completed = detail_workflow_service.resolve_detail_completed(
        natures,
        workflow,
        manual_value=manual_detail_completed,
    )
    return design_completed, detail_completed


def format_customer_from_personnel_ids(personnel_ids: list[str]) -> str:
    if not personnel_ids:
        return ""
    placeholders = ", ".join(f":p{i}" for i in range(len(personnel_ids)))
    params = {f"p{i}": value for i, value in enumerate(personnel_ids)}
    rows = db.session.execute(
        text(f"SELECT name FROM personnel WHERE id IN ({placeholders}) ORDER BY LOWER(name)"),
        params,
    ).all()
    return "、".join(row.name for row in rows)


def build_work_paths(payload: dict, existing: dict | None = None) -> tuple[str, str, str]:
    existing_design = normalize_relative_path((existing or {}).get("design_work_path") or "")
    existing_detail = normalize_relative_path((existing or {}).get("detail_work_path") or "")
    existing_local = normalize_relative_path((existing or {}).get("local_work_path") or "")

    design_work_path = (
        normalize_relative_path(payload.get("designWorkPath") or "")
        if payload.get("designWorkPath") is not None
        else existing_design
    )
    detail_work_path = (
        normalize_relative_path(payload.get("detailWorkPath") or "")
        if payload.get("detailWorkPath") is not None
        else existing_detail
    )

    if payload.get("localWorkPath") is not None:
        legacy_local = normalize_relative_path(payload.get("localWorkPath") or "")
        if not design_work_path and not detail_work_path:
            detail_work_path = legacy_local
        local_work_path = legacy_local
    else:
        local_work_path = detail_work_path or design_work_path or existing_local

    return design_work_path, detail_work_path, local_work_path


def sync_project_natures(project_no: str, natures: list[str]) -> None:
    db.session.execute(
        text("DELETE FROM project_natures WHERE project_no = :project_no"),
        {"project_no": project_no},
    )
    for nature in natures:
        db.session.execute(
            text(
                insert_ignore("project_natures", "project_no, nature") + " VALUES (:project_no, :nature)"
            ),
            {"project_no": project_no, "nature": nature},
        )


def sync_project_personnel(project_no: str, personnel_ids: list[str]) -> None:
    db.session.execute(
        text("DELETE FROM project_personnel WHERE project_no = :project_no"),
        {"project_no": project_no},
    )
    for personnel_id in personnel_ids:
        db.session.execute(
            text(
                insert_ignore("project_personnel", "project_no, personnel_id") + " VALUES (:project_no, :personnel_id)"
            ),
            {"project_no": project_no, "personnel_id": personnel_id},
        )


def get_contact_received_date(contact_form_id: str) -> str:
    row = db.session.execute(
        text("SELECT received_date FROM contact_forms WHERE id = :id"),
        {"id": contact_form_id},
    ).first()
    return (row.received_date or "").strip() if row else ""


def list_projects(
    *,
    keyword: str = "",
    status: str = "",
    assigned_personnel_id: str = "",
    tag_ids: list[str] | None = None,
    nature_filters: list[str] | None = None,
    flow_filters: list[str] | None = None,
    personnel_team: str = "",
    exclude_project_nos: list[str] | None = None,
    page_query: ListPageQuery,
    load_all: bool = False,
) -> dict:
    keyword = keyword.strip().lower()
    conditions, params = _build_project_conditions(
        keyword,
        status,
        assigned_personnel_id,
        tag_ids,
        nature_filters=nature_filters,
        flow_filters=flow_filters,
        personnel_team=personnel_team,
        exclude_project_nos=exclude_project_nos,
    )
    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    # COUNT 查询
    total = db.session.execute(
        text(f"SELECT COUNT(*) FROM projects p {where_clause}"),
        params,
    ).scalar_one()

    if load_all:
        rows = db.session.execute(
            text(f"SELECT p.* FROM projects p {where_clause} ORDER BY {PROJECT_LIST_ORDER}"),
            params,
        ).all()
        items = map_projects_batch([_row_to_dict(row) for row in rows])
        return {
            "list": items,
            "total": total,
            "page": 1,
            "pageSize": len(items),
            "totalPages": 1,
        }

    anchor_index = None
    if page_query.anchor:
        resolved_anchor = resolve_project_anchor(page_query.anchor)
        anchor_index = get_project_rank(where_clause, params, resolved_anchor)

    window = compute_paginated_window(
        total=total,
        page_size=page_query.page_size,
        page=None if page_query.anchor else page_query.page,
        anchor_index=anchor_index,
    )

    rows = db.session.execute(
        text(f"SELECT p.* FROM projects p {where_clause} ORDER BY {PROJECT_LIST_ORDER} LIMIT :limit OFFSET :offset"),
        {**params, "limit": window.limit, "offset": window.offset},
    ).all()

    return {
        "list": map_projects_batch([_row_to_dict(row) for row in rows]),
        "total": total,
        "page": window.page,
        "pageSize": page_query.page_size,
        "totalPages": window.total_pages,
    }


def check_project_nos(project_nos: list[str]) -> dict:
    unique = list(dict.fromkeys(item.strip() for item in project_nos if item and item.strip()))
    if not unique:
        return {"existing": [], "exact": []}

    existing: set[str] = set()
    exact: set[str] = set()
    placeholders = ", ".join(f":p{i}" for i in range(len(unique)))
    params = {f"p{i}": value for i, value in enumerate(unique)}
    rows = db.session.execute(
        text(f"SELECT project_no FROM projects WHERE project_no IN ({placeholders})"),
        params,
    ).all()
    exact.update(row.project_no for row in rows)
    existing.update(exact)

    for project_no in unique:
        if project_no in existing:
            continue

        resolved = resolve_project_no(project_no)
        if resolved != project_no and Project.query.get(resolved):
            existing.add(project_no)
            continue

        orphan = db.session.execute(
            text(
                """
                SELECT 1
                FROM contact_form_projects cfp
                INNER JOIN contact_forms cf ON cf.id = cfp.contact_form_id
                WHERE cf.deleted_at IS NULL
                  AND cfp.project_no = :project_no
                LIMIT 1
                """
            ),
            {"project_no": resolved},
        ).first()
        if orphan:
            existing.add(project_no)

    return {"existing": sorted(existing), "exact": sorted(exact)}


def _relink_contact_to_project(contact_form_id: str, project_no: str) -> None:
    project_no = resolve_project_no(project_no)
    contact_form_id = (contact_form_id or "").strip()
    if not project_no or not contact_form_id:
        return

    db.session.execute(
        text("DELETE FROM contact_form_projects WHERE contact_form_id = :contact_form_id"),
        {"contact_form_id": contact_form_id},
    )
    db.session.execute(
        text(
	            insert_ignore("contact_form_projects", "contact_form_id, project_no")
	            + " VALUES (:contact_form_id, :project_no)"
        ),
        {"contact_form_id": contact_form_id, "project_no": project_no},
    )


def normalize_contact_form_ids(raw_ids: list | None) -> tuple[list[str], str | None]:
    if raw_ids is None:
        return [], None

    normalized: list[str] = []
    seen: set[str] = set()
    for item in raw_ids:
        contact_id = (item or "").strip()
        if not contact_id:
            continue
        if contact_id in seen:
            continue
        seen.add(contact_id)
        normalized.append(contact_id)
    return normalized, None


def sync_project_contact_forms(project_no: str, contact_form_ids: list[str]) -> str | None:
    project_no = resolve_project_no(project_no)
    if not project_no:
        return "项目号不能为空"

    for contact_id in contact_form_ids:
        row = db.session.execute(
            text("SELECT id FROM contact_forms WHERE id = :id AND deleted_at IS NULL"),
            {"id": contact_id},
        ).first()
        if row is None:
            return f"联系单 {contact_id} 不存在"

    current_ids = set(get_contact_form_ids(project_no))
    desired_ids = set(contact_form_ids)

    for contact_id in current_ids - desired_ids:
        db.session.execute(
            text(
                """
                DELETE FROM contact_form_projects
                WHERE project_no = :project_no AND contact_form_id = :contact_form_id
                """
            ),
            {"project_no": project_no, "contact_form_id": contact_id},
        )

    for contact_id in desired_ids - current_ids:
        db.session.execute(
            text(
                insert_ignore("contact_form_projects", "contact_form_id, project_no, source_type, source_contact_form_id")
                + " VALUES (:contact_form_id, :project_no, 'own', NULL)"
            ),
            {"contact_form_id": contact_id, "project_no": project_no},
        )

    recompute_derived_received_date(project_no)
    return None


_PROJECT_NO_CHILD_TABLES = (
    "project_natures",
    "project_personnel",
    "contact_form_projects",
    "contact_form_project_cancellations",
    "project_detail_workflows",
    "project_design_workflows",
    "project_tags",
)


def _rename_project_no(old_no: str, new_no: str) -> str | None:
    """将项目主键及关联表中的 project_no 从 old_no 迁移到 new_no。"""
    if old_no == new_no:
        return None

    if Project.query.get(new_no) is not None:
        return f"项目号 {new_no} 已存在"

    old_project = Project.query.get(old_no)
    if old_project is None:
        return "项目不存在"

    now_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    new_project = Project(
        project_no=new_no,
        name=old_project.name,
        customer=old_project.customer,
        status=old_project.status,
        design_completed=old_project.design_completed,
        detail_completed=old_project.detail_completed,
        tile_layout_completed=old_project.tile_layout_completed,
        floor_deck_layout_completed=old_project.floor_deck_layout_completed,
        received_date=old_project.received_date,
        planned_start_date=old_project.planned_start_date,
        planned_end_date=old_project.planned_end_date,
        actual_start_date=old_project.actual_start_date,
        actual_end_date=old_project.actual_end_date,
        design_work_path=old_project.design_work_path,
        detail_work_path=old_project.detail_work_path,
        local_work_path=old_project.local_work_path,
        created_at=old_project.created_at,
        updated_at=now_text,
    )
    db.session.add(new_project)
    db.session.flush()

    for table in _PROJECT_NO_CHILD_TABLES:
        db.session.execute(
            text(f"UPDATE {table} SET project_no = :new_no WHERE project_no = :old_no"),
            {"new_no": new_no, "old_no": old_no},
        )

    db.session.execute(
        text(
            "UPDATE temp_tasks SET related_project_no = :new_no "
            "WHERE related_project_no = :old_no"
        ),
        {"new_no": new_no, "old_no": old_no},
    )
    db.session.execute(
        text(
            "UPDATE design_drawing_issue_plans SET project_no = :new_no "
            "WHERE project_no = :old_no"
        ),
        {"new_no": new_no, "old_no": old_no},
    )
    db.session.execute(
        text(
            "UPDATE drawing_issue_plans SET project_no = :new_no "
            "WHERE project_no = :old_no"
        ),
        {"new_no": new_no, "old_no": old_no},
    )

    db.session.delete(old_project)
    db.session.flush()
    return None


def _collect_hyphen_split_family(root: str) -> set[str]:
    root = parse_hyphen_root(root)
    existing: set[str] = set()
    if Project.query.get(root):
        existing.add(root)
    rows = db.session.execute(
        text("SELECT project_no FROM projects WHERE project_no LIKE :pattern"),
        {"pattern": f"{root}-%"},
    ).all()
    for row in rows:
        project_no = str(row.project_no)
        if has_hyphen_split_suffix(project_no):
            existing.add(project_no)
    return existing


def _next_hyphen_split_project_no(root: str, *, exclude: set[str] | None = None) -> str:
    root = parse_hyphen_root(root)
    existing = _collect_hyphen_split_family(root)
    if exclude:
        existing |= exclude
    index = 1
    while f"{root}-{index}" in existing:
        index += 1
    return f"{root}-{index}"


def _clone_project_from(
    source_no: str,
    target_no: str,
    *,
    copy_contacts: bool = False,
    clear_actual_dates: bool = False,
) -> str | None:
    source = Project.query.get(source_no)
    if source is None:
        return "源项目不存在"
    if Project.query.get(target_no):
        return f"项目号 {target_no} 已存在"

    now_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    project = Project(
        project_no=target_no,
        name=source.name,
        customer=source.customer,
        status=source.status,
        design_completed=source.design_completed,
        detail_completed=source.detail_completed,
        tile_layout_completed=source.tile_layout_completed,
        floor_deck_layout_completed=source.floor_deck_layout_completed,
        drawing_issue_enabled=source.drawing_issue_enabled,
        drawing_issue_year_month=source.drawing_issue_year_month,
        received_date=source.received_date,
        planned_start_date=source.planned_start_date,
        planned_end_date=source.planned_end_date,
        actual_start_date="" if clear_actual_dates else source.actual_start_date,
        actual_end_date="" if clear_actual_dates else source.actual_end_date,
        design_work_path=source.design_work_path,
        detail_work_path=source.detail_work_path,
        local_work_path=source.local_work_path,
        created_at=now_text,
        updated_at=now_text,
    )
    db.session.add(project)
    db.session.flush()

    for row in db.session.execute(
        text("SELECT nature, created_at FROM project_natures WHERE project_no = :project_no"),
        {"project_no": source_no},
    ):
        db.session.execute(
            text(
                insert_ignore("project_natures", "project_no, nature, created_at")
                + " VALUES (:project_no, :nature, :created_at)"
            ),
            {
                "project_no": target_no,
                "nature": row.nature,
                "created_at": row.created_at,
            },
        )

    for row in db.session.execute(
        text("SELECT personnel_id, created_at FROM project_personnel WHERE project_no = :project_no"),
        {"project_no": source_no},
    ):
        db.session.execute(
            text(
                insert_ignore("project_personnel", "project_no, personnel_id, created_at")
                + " VALUES (:project_no, :personnel_id, :created_at)"
            ),
            {
                "project_no": target_no,
                "personnel_id": row.personnel_id,
                "created_at": row.created_at,
            },
        )

    for row in db.session.execute(
        text("SELECT tag_id, created_at FROM project_tags WHERE project_no = :project_no"),
        {"project_no": source_no},
    ):
        db.session.execute(
            text(
                insert_ignore("project_tags", "project_no, tag_id, created_at")
                + " VALUES (:project_no, :tag_id, :created_at)"
            ),
            {
                "project_no": target_no,
                "tag_id": row.tag_id,
                "created_at": row.created_at,
            },
        )

    detail_workflow = ProjectDetailWorkflow.query.get(source_no)
    if detail_workflow is not None:
        db.session.add(
            ProjectDetailWorkflow(
                project_no=target_no,
                modeling_status=detail_workflow.modeling_status,
                drawing_status=detail_workflow.drawing_status,
                plate_layout_enabled=detail_workflow.plate_layout_enabled,
                plate_layout_status=detail_workflow.plate_layout_status,
                modeling_started_at=detail_workflow.modeling_started_at,
                modeling_completed_at=detail_workflow.modeling_completed_at,
                drawing_started_at=detail_workflow.drawing_started_at,
                drawing_completed_at=detail_workflow.drawing_completed_at,
                plate_layout_started_at=detail_workflow.plate_layout_started_at,
                plate_layout_completed_at=detail_workflow.plate_layout_completed_at,
                model_weight_tons=detail_workflow.model_weight_tons,
                model_weight_updated_at=detail_workflow.model_weight_updated_at,
                model_weight_updated_by=detail_workflow.model_weight_updated_by,
                created_at=now_text,
                updated_at=now_text,
            )
        )

    design_workflow = ProjectDesignWorkflow.query.get(source_no)
    if design_workflow is not None:
        db.session.add(
            ProjectDesignWorkflow(
                project_no=target_no,
                design_started_at=design_workflow.design_started_at,
                design_completed_at=design_workflow.design_completed_at,
                created_at=now_text,
                updated_at=now_text,
            )
        )

    if copy_contacts:
        for row in db.session.execute(
            text(
                "SELECT contact_form_id, source_type, source_contact_form_id, created_at "
                "FROM contact_form_projects WHERE project_no = :project_no"
            ),
            {"project_no": source_no},
        ):
            db.session.execute(
                text(
                    insert_ignore("contact_form_projects", "contact_form_id, project_no, source_type, source_contact_form_id, created_at")
                    + " VALUES (:contact_form_id, :project_no, :source_type, :source_contact_form_id, :created_at)"
                ),
                {
                    "contact_form_id": row.contact_form_id,
                    "project_no": target_no,
                    "source_type": row.source_type,
                    "source_contact_form_id": row.source_contact_form_id,
                    "created_at": row.created_at,
                },
            )

    db.session.flush()
    return None


def _get_project_row(project_no: str):
    return Project.query.get(project_no)


def copy_project(source_no: str, payload: dict) -> tuple[dict | None, str | None, int]:
    source_no = (source_no or "").strip()
    if not Project.query.get(source_no):
        return None, "源项目不存在", 404

    raw_target_no = (payload.get("projectNo") or "").strip()
    target_no = raw_target_no or _next_hyphen_split_project_no(parse_hyphen_root(source_no))
    if is_split_project_no(target_no):
        return None, "项目号不应包含 ~ 或 # 拆分后缀", 400
    if Project.query.get(target_no):
        return None, f"项目号 {target_no} 已存在", 409

    clear_actual_dates = normalize_completion_flag(payload.get("clearActualDates"), default=True)
    clone_error = _clone_project_from(
        source_no,
        target_no,
        copy_contacts=False,
        clear_actual_dates=clear_actual_dates,
    )
    if clone_error:
        return None, clone_error, 400

    update_fields = {
        key: payload[key]
        for key in (
            "projectNo",
            "name",
            "status",
            "designCompleted",
            "detailCompleted",
            "natures",
            "tagIds",
            "assignedPersonnelIds",
            "plannedStartDate",
            "plannedEndDate",
            "actualStartDate",
            "actualEndDate",
            "designWorkPath",
            "detailWorkPath",
            "localWorkPath",
            "drawingIssueEnabled",
            "drawingIssueYearMonth",
        )
        if key in payload
    }
    if update_fields:
        result, error, status = update_project(target_no, update_fields)
        if error:
            db.session.rollback()
            return None, error, status
        return result, None, 201

    db.session.commit()
    row = _get_project_row(target_no)
    return map_project(_row_to_dict(row)), None, 201


def split_project(source_no: str) -> tuple[dict | None, str | None, int]:
    source_no = (source_no or "").strip()
    if not Project.query.get(source_no):
        return None, "项目不存在", 404

    root = parse_hyphen_root(source_no)
    working_no = source_no

    if not has_hyphen_split_suffix(source_no):
        first_no = f"{root}-1"
        if Project.query.get(first_no):
            return None, f"项目号 {first_no} 已存在，无法自动拆分", 409
        rename_error = _rename_project_no(source_no, first_no)
        if rename_error:
            return None, rename_error, 400
        working_no = first_no

    clone_no = _next_hyphen_split_project_no(root, exclude={working_no})
    clone_error = _clone_project_from(
        working_no,
        clone_no,
        copy_contacts=False,
        clear_actual_dates=False,
    )
    if clone_error:
        db.session.rollback()
        return None, clone_error, 400

    db.session.commit()
    original_row = _get_project_row(working_no)
    clone_row = _get_project_row(clone_no)
    if original_row is None or clone_row is None:
        return None, "拆分后项目读取失败", 500

    return (
        {
            "original": map_project(_row_to_dict(original_row)),
            "clone": map_project(_row_to_dict(clone_row)),
        },
        None,
        200,
    )


def create_project(payload: dict) -> tuple[dict | None, str | None, int]:
    raw_project_no = (payload.get("projectNo") or "").strip()
    project_no = resolve_project_no(raw_project_no)
    if not project_no:
        return None, "项目号不能为空", 400
    if is_split_project_no(raw_project_no):
        return None, "项目号不应包含拆分后缀，请使用业务项目号", 400
    if Project.query.get(project_no):
        return None, f"项目号 {project_no} 已存在", 409

    natures, nature_error = normalize_natures(payload.get("natures"))
    if nature_error:
        return None, nature_error, 400

    assignee_ids, assignee_error = normalize_assigned_personnel_ids(payload.get("assignedPersonnelIds"))
    if assignee_error:
        return None, assignee_error, 400

    name = (payload.get("name") or "").strip() or project_no
    status, status_error = normalize_project_status(payload.get("status"))
    if status_error:
        return None, status_error, 400
    design_completed, detail_completed = build_completion_flags(payload, natures or [])
    design_work_path, detail_work_path, local_work_path = build_work_paths(payload)
    contact_form_id = (payload.get("contactFormId") or "").strip()
    planned_start = (payload.get("plannedStartDate") or "").strip()
    received_date = planned_start or (get_contact_received_date(contact_form_id) if contact_form_id else "")
    drawing_issue_enabled = normalize_completion_flag(payload.get("drawingIssueEnabled"))
    drawing_issue_year_month = ""
    if drawing_issue_enabled:
        drawing_issue_year_month, year_month_error = normalize_drawing_issue_year_month(
            payload.get("drawingIssueYearMonth")
        )
        if year_month_error:
            return None, year_month_error, 400

    project = Project(
        project_no=project_no,
        name=name,
        customer=format_customer_from_personnel_ids(assignee_ids or []),
        status=status,
        design_completed=design_completed,
        detail_completed=detail_completed,
        drawing_issue_enabled=drawing_issue_enabled,
        drawing_issue_year_month=drawing_issue_year_month,
        received_date=received_date,
        planned_start_date=planned_start,
        planned_end_date=(payload.get("plannedEndDate") or "").strip(),
        actual_start_date=(payload.get("actualStartDate") or "").strip(),
        actual_end_date=(payload.get("actualEndDate") or "").strip(),
        design_work_path=design_work_path,
        detail_work_path=detail_work_path,
        local_work_path=local_work_path,
    )
    db.session.add(project)
    sync_project_natures(project_no, natures or [])
    sync_project_personnel(project_no, assignee_ids or [])
    if "tagIds" in payload:
        tag_ids, tag_error = tag_service.normalize_tag_ids(payload.get("tagIds"))
        if tag_error:
            return None, tag_error, 400
        tag_service.sync_project_tags(project_no, tag_ids)
    workflow = detail_workflow_service.ensure_detail_workflow(project_no, natures or [])
    design_workflow_service.ensure_design_workflow(project_no, natures or [])
    _, detail_completed = build_completion_flags(payload, natures or [], workflow=workflow)
    project.detail_completed = detail_completed
    _sync_project_process_status_from_completion(project, natures or [], workflow)

    if contact_form_id:
        exists = db.session.execute(
            text("SELECT id FROM contact_forms WHERE id = :id AND deleted_at IS NULL"),
            {"id": contact_form_id},
        ).first()
        if exists:
            _relink_contact_to_project(contact_form_id, project_no)

    db.session.commit()
    recompute_derived_received_date(project_no)
    row = Project.query.get(project_no)
    return map_project(_row_to_dict(row)), None, 201


def update_project(project_no: str, payload: dict) -> tuple[dict | None, str | None, int]:
    row = Project.query.get(project_no)
    if row is None:
        return None, "项目不存在", 404

    existing = _row_to_dict(row)
    if "name" in payload:
        name = (payload.get("name") or "").strip()
    else:
        name = (existing.get("name") or "").strip()
    if not name:
        return None, "项目名称不能为空", 400

    natures, nature_error = normalize_natures(payload.get("natures") or get_project_natures(project_no))
    if nature_error:
        return None, nature_error, 400

    default_assignees = [item["id"] for item in get_assigned_personnel(project_no)]
    assignee_ids, assignee_error = normalize_assigned_personnel_ids(
        payload.get("assignedPersonnelIds") or default_assignees
    )
    if assignee_error:
        return None, assignee_error, 400

    existing_dates = map_project_dates(existing)
    project = Project.query.get(project_no)
    assert project is not None

    project.name = name
    project.customer = format_customer_from_personnel_ids(assignee_ids or [])
    status_set_to_done = False
    if "status" in payload:
        status, status_error = normalize_project_status(
            payload.get("status"),
            default=(existing.get("status") or "active"),
        )
        if status_error:
            return None, status_error, 400
        project.status = status
        status_set_to_done = status == PROJECT_STATUS_DONE
    project.planned_start_date = (
        (payload.get("plannedStartDate") or "").strip()
        if payload.get("plannedStartDate") is not None
        else existing_dates["plannedStartDate"]
    )
    project.planned_end_date = (
        (payload.get("plannedEndDate") or "").strip()
        if payload.get("plannedEndDate") is not None
        else existing_dates["plannedEndDate"]
    )
    project.actual_start_date = (
        (payload.get("actualStartDate") or "").strip()
        if payload.get("actualStartDate") is not None
        else existing_dates["actualStartDate"]
    )
    project.actual_end_date = (
        (payload.get("actualEndDate") or "").strip()
        if payload.get("actualEndDate") is not None
        else existing_dates["actualEndDate"]
    )
    design_work_path, detail_work_path, local_work_path = build_work_paths(payload, existing)
    project.design_work_path = design_work_path
    project.detail_work_path = detail_work_path
    project.local_work_path = local_work_path

    sync_project_natures(project_no, natures or [])
    sync_project_personnel(project_no, assignee_ids or [])
    if "tagIds" in payload:
        tag_ids, tag_error = tag_service.normalize_tag_ids(payload.get("tagIds"))
        if tag_error:
            return None, tag_error, 400
        tag_service.sync_project_tags(project_no, tag_ids)
    if "contactFormIds" in payload:
        contact_form_ids, contact_ids_error = normalize_contact_form_ids(payload.get("contactFormIds"))
        if contact_ids_error:
            return None, contact_ids_error, 400
        contact_sync_error = sync_project_contact_forms(project_no, contact_form_ids)
        if contact_sync_error:
            return None, contact_sync_error, 400
    workflow = detail_workflow_service.ensure_detail_workflow(project_no, natures or [])
    design_workflow_service.ensure_design_workflow(project_no, natures or [])
    design_completed, detail_completed = build_completion_flags(payload, natures or [], existing, workflow)
    project.design_completed = design_completed
    project.detail_completed = detail_completed
    project.tile_layout_completed = normalize_completion_flag(
        payload.get("tileLayoutCompleted"), default=normalize_completion_flag((existing or {}).get("tile_layout_completed"))
    )
    project.floor_deck_layout_completed = normalize_completion_flag(
        payload.get("floorDeckLayoutCompleted"), default=normalize_completion_flag((existing or {}).get("floor_deck_layout_completed"))
    )
    if status_set_to_done:
        _apply_process_done_progress(project, natures or [], workflow)
    else:
        _sync_project_process_status_from_completion(project, natures or [], workflow)
    if "drawingIssueEnabled" in payload:
        drawing_issue_enabled = normalize_completion_flag(payload.get("drawingIssueEnabled"))
        project.drawing_issue_enabled = drawing_issue_enabled
        if drawing_issue_enabled:
            drawing_issue_year_month, year_month_error = normalize_drawing_issue_year_month(
                payload.get("drawingIssueYearMonth"),
                default=(existing.get("drawing_issue_year_month") or "").strip(),
            )
            if year_month_error:
                return None, year_month_error, 400
            project.drawing_issue_year_month = drawing_issue_year_month
        else:
            project.drawing_issue_year_month = ""
    elif "drawingIssueYearMonth" in payload:
        drawing_issue_enabled = normalize_completion_flag(existing.get("drawing_issue_enabled"))
        if drawing_issue_enabled:
            drawing_issue_year_month, year_month_error = normalize_drawing_issue_year_month(
                payload.get("drawingIssueYearMonth"),
                default=(existing.get("drawing_issue_year_month") or "").strip(),
            )
            if year_month_error:
                return None, year_month_error, 400
            project.drawing_issue_year_month = drawing_issue_year_month

    target_project_no = project_no
    if "projectNo" in payload:
        raw_new_no = (payload.get("projectNo") or "").strip()
        new_project_no = resolve_project_no(raw_new_no)
        if not new_project_no:
            return None, "项目号不能为空", 400
        if is_split_project_no(raw_new_no):
            return None, "项目号不应包含拆分后缀，请使用业务项目号", 400
        if new_project_no != project_no:
            db.session.flush()
            rename_error = _rename_project_no(project_no, new_project_no)
            if rename_error:
                status = 409 if "已存在" in rename_error else 400
                return None, rename_error, status
            target_project_no = new_project_no

    db.session.commit()
    recompute_derived_received_date(target_project_no)

    updated = Project.query.get(target_project_no)
    return map_project(_row_to_dict(updated)), None, 200


def delete_project(project_no: str) -> bool:
    project = Project.query.get(project_no)
    if project is None:
        return False
    db.session.delete(project)
    db.session.commit()
    return True


def leave_project_assignment(
    project_no: str,
    *,
    target_personnel_id: str,
    editor_personnel_id: str | None = None,
    editor_is_admin: bool = False,
) -> tuple[dict | None, str | None, int]:
    """将指定人员从项目分配中移除（我的页面退出非本人负责的项目）"""
    personnel_id = (target_personnel_id or "").strip()
    if not personnel_id:
        return None, "人员ID不能为空", 400

    if not editor_is_admin and editor_personnel_id != personnel_id:
        return None, "无权替他人退出项目", 403

    row = Project.query.get(project_no)
    if row is None:
        return None, "项目不存在", 404

    assigned = get_assigned_personnel(project_no)
    if not any(item["id"] == personnel_id for item in assigned):
        return None, "该人员未参与此项目", 400

    person = Personnel.query.get(personnel_id)
    if person is None:
        return None, "人员不存在", 404

    team = (person.team or "").strip()
    team_assignees = [item for item in assigned if (item.get("team") or "").strip() == team]
    if len(team_assignees) == 1 and team_assignees[0]["id"] == personnel_id:
        return None, "无法退出本人负责的项目", 400

    next_ids = [item["id"] for item in assigned if item["id"] != personnel_id]
    sync_project_personnel(project_no, next_ids)

    project = Project.query.get(project_no)
    if project is not None:
        project.customer = format_customer_from_personnel_ids(next_ids)

    db.session.commit()

    updated = Project.query.get(project_no)
    return map_project(_row_to_dict(updated)), None, 200


def has_dual_nature_tasks(natures: list[str]) -> bool:
    """与前端 ProjectForm.hasDualNatureTasks 对齐：同时含设计与细化主任务。"""
    return "design" in natures and "detail" in natures


def _completion_sync_kind(natures: list[str]) -> str | None:
    """单主任务项目返回 design/detail，双主任务或无关项目返回 None。"""
    if has_dual_nature_tasks(natures):
        return None
    if "design" in natures:
        return "design"
    if "detail" in natures:
        return "detail"
    return None


def _is_primary_workflow_completed(
    project: Project,
    sync_kind: str,
    natures: list[str],
    workflow: ProjectDetailWorkflow | None = None,
) -> bool:
    if sync_kind == "design":
        return bool(project.design_completed)
    return detail_workflow_service.is_detail_process_completed(
        natures,
        workflow,
        manual_value=bool(project.detail_completed),
    )


def _sync_project_process_status_from_completion(
    project: Project,
    natures: list[str],
    workflow: ProjectDetailWorkflow | None = None,
) -> None:
    """仅设计或仅细化项目：主任务完成时自动将流程状态置为已完成。"""
    sync_kind = _completion_sync_kind(natures)
    if sync_kind is None:
        return

    if workflow is None and detail_workflow_service.needs_detail_workflow(natures):
        workflow = detail_workflow_service.get_detail_workflow(project.project_no)

    completed = _is_primary_workflow_completed(project, sync_kind, natures, workflow)
    if completed:
        if project.status == PROJECT_STATUS_ACTIVE:
            project.status = PROJECT_STATUS_DONE
            if not (project.actual_end_date or "").strip():
                project.actual_end_date = datetime.now().strftime("%Y-%m-%d")
    elif project.status == PROJECT_STATUS_DONE:
        project.status = PROJECT_STATUS_ACTIVE
        project.actual_end_date = ""


def _apply_process_done_progress(
    project: Project,
    natures: list[str],
    workflow: ProjectDetailWorkflow | None = None,
) -> None:
    """流程状态手动置为已完成时，按项目性质级联完成对应进度。"""
    if "design" in natures:
        project.design_completed = True
        design_workflow = design_workflow_service.ensure_design_workflow(project.project_no, natures)
        if design_workflow is not None:
            design_workflow_service.mark_design_completed(design_workflow)

    if detail_workflow_service.needs_detail_workflow(natures):
        if workflow is None:
            workflow = detail_workflow_service.ensure_detail_workflow(project.project_no, natures)
        if workflow is not None:
            detail_workflow_service.mark_main_flow_completed(workflow)
            project.detail_completed = detail_workflow_service.resolve_detail_completed(
                natures,
                workflow,
            )
    elif "detail" in natures or "detail_issue" in natures:
        project.detail_completed = True

    if "tile_layout" in natures:
        project.tile_layout_completed = True
    if "floor_deck_layout" in natures:
        project.floor_deck_layout_completed = True

    if not (project.actual_end_date or "").strip():
        project.actual_end_date = datetime.now().strftime("%Y-%m-%d")


def _sync_project_after_workflow_change(project: Project, natures: list[str], workflow) -> None:
    project.detail_completed = detail_workflow_service.resolve_detail_completed(natures, workflow)
    _sync_project_process_status_from_completion(project, natures, workflow)


def apply_detail_workflow_action(project_no: str, action: str) -> tuple[dict | None, str | None, int]:
    row = Project.query.get(project_no)
    if row is None:
        return None, "项目不存在", 404

    natures = get_project_natures(project_no)
    workflow, error = detail_workflow_service.apply_workflow_action(project_no, action, natures)
    if error:
        return None, error, 400

    project = Project.query.get(project_no)
    assert project is not None
    _sync_project_after_workflow_change(project, natures, workflow)

    db.session.commit()

    updated = Project.query.get(project_no)
    return map_project(_row_to_dict(updated)), None, 200


def save_detail_workflow(project_no: str, payload: dict) -> tuple[dict | None, str | None, int]:
    row = Project.query.get(project_no)
    if row is None:
        return None, "项目不存在", 404

    natures = get_project_natures(project_no)
    workflow, error = detail_workflow_service.update_detail_workflow(project_no, payload, natures)
    if error:
        return None, error, 400

    project = Project.query.get(project_no)
    assert project is not None
    _sync_project_after_workflow_change(project, natures, workflow)

    db.session.commit()

    updated = Project.query.get(project_no)
    return map_project(_row_to_dict(updated)), None, 200


def save_model_weight(project_no: str, payload: dict) -> tuple[dict | None, str | None, int]:
    row = Project.query.get(project_no)
    if row is None:
        return None, "项目不存在", 404

    natures = get_project_natures(project_no)
    workflow, error = detail_workflow_service.update_model_weight_from_request(
        project_no, payload, natures
    )
    if error:
        return None, error, 400

    project = Project.query.get(project_no)
    assert project is not None
    _sync_project_after_workflow_change(project, natures, workflow)

    db.session.commit()

    updated = Project.query.get(project_no)
    return map_project(_row_to_dict(updated)), None, 200


def save_design_workflow(project_no: str, payload: dict) -> tuple[dict | None, str | None, int]:
    row = Project.query.get(project_no)
    if row is None:
        return None, "项目不存在", 404

    natures = get_project_natures(project_no)
    _, error = design_workflow_service.update_design_workflow(project_no, payload, natures)
    if error:
        return None, error, 400

    db.session.commit()

    updated = Project.query.get(project_no)
    return map_project(_row_to_dict(updated)), None, 200
