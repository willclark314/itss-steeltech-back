from __future__ import annotations

from sqlalchemy import text

from steeltech_db.extensions import db
from steeltech_db.models import ContactFormProject, Personnel, Project, ProjectNature
from app.utils.pagination import ListPageQuery, compute_paginated_window
from app.utils.paths import normalize_relative_path

VALID_NATURES = frozenset({"design", "detail"})


def _row_to_dict(row) -> dict:
    return dict(row._mapping)


def get_contact_form_ids(project_no: str) -> list[str]:
    rows = (
        ContactFormProject.query.filter_by(project_no=project_no)
        .order_by(ContactFormProject.contact_form_id)
        .all()
    )
    return [row.contact_form_id for row in rows]


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


def map_project(row: dict) -> dict:
    project_no = row["project_no"]
    assigned = get_assigned_personnel(project_no)
    dates = map_project_dates(row)
    return {
        "projectNo": project_no,
        "name": row["name"],
        "customer": row.get("customer") or "",
        "status": row["status"],
        "natures": get_project_natures(project_no),
        "assignedPersonnelIds": [item["id"] for item in assigned],
        "assignedPersonnel": assigned,
        "receivedDate": resolve_received_date(row),
        **dates,
        "localWorkPath": normalize_relative_path(row.get("local_work_path") or ""),
        "contactFormIds": get_contact_form_ids(project_no),
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


def _get_contact_ids_map(project_nos: list[str]) -> dict[str, list[str]]:
    if not project_nos:
        return {}
    placeholders = ", ".join(f":p{i}" for i in range(len(project_nos)))
    params = {f"p{i}": value for i, value in enumerate(project_nos)}
    rows = db.session.execute(
        text(
            f"""
            SELECT project_no, contact_form_id
            FROM contact_form_projects
            WHERE project_no IN ({placeholders})
            ORDER BY contact_form_id
            """
        ),
        params,
    ).all()
    result: dict[str, list[str]] = {}
    for row in rows:
        result.setdefault(row.project_no, []).append(row.contact_form_id)
    return result


def map_projects_batch(rows: list[dict]) -> list[dict]:
    project_nos = [row["project_no"] for row in rows]
    natures_map = _get_natures_map(project_nos)
    personnel_map = _get_personnel_map(project_nos)
    contact_map = _get_contact_ids_map(project_nos)
    result = []
    for row in rows:
        assigned = personnel_map.get(row["project_no"], [])
        dates = map_project_dates(row)
        result.append(
            {
                "projectNo": row["project_no"],
                "name": row["name"],
                "customer": row.get("customer") or "",
                "status": row["status"],
                "natures": natures_map.get(row["project_no"], []),
                "assignedPersonnelIds": [item["id"] for item in assigned],
                "assignedPersonnel": assigned,
                "receivedDate": resolve_received_date(row),
                **dates,
                "localWorkPath": normalize_relative_path(row.get("local_work_path") or ""),
                "contactFormIds": contact_map.get(row["project_no"], []),
            }
        )
    return result


def build_project_filters(keyword: str, status: str) -> tuple[str, dict]:
    conditions: list[str] = []
    params: dict = {}

    if status:
        conditions.append("p.status = :status")
        params["status"] = status

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
                    OR (:raw_kw LIKE '%细化%' AND pn.nature = 'detail')
                  )
              )
            )"""
        )
        params["kw"] = f"%{keyword}%"
        params["raw_kw"] = keyword

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    return where_clause, params


def get_project_rank(where_clause: str, params: dict, project_no: str) -> int | None:
    row = db.session.execute(
        text(
            f"""
            WITH ranked AS (
              SELECT p.project_no, ROW_NUMBER() OVER (ORDER BY p.project_no ASC) - 1 AS rank
              FROM projects p
              {where_clause}
            )
            SELECT rank FROM ranked WHERE project_no = :project_no
            """
        ),
        {**params, "project_no": project_no},
    ).first()
    return int(row.rank) if row else None


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


def format_customer_from_personnel_ids(personnel_ids: list[str]) -> str:
    if not personnel_ids:
        return ""
    placeholders = ", ".join(f":p{i}" for i in range(len(personnel_ids)))
    params = {f"p{i}": value for i, value in enumerate(personnel_ids)}
    rows = db.session.execute(
        text(f"SELECT name FROM personnel WHERE id IN ({placeholders}) ORDER BY name COLLATE NOCASE"),
        params,
    ).all()
    return "、".join(row.name for row in rows)


def sync_project_natures(project_no: str, natures: list[str]) -> None:
    db.session.execute(
        text("DELETE FROM project_natures WHERE project_no = :project_no"),
        {"project_no": project_no},
    )
    for nature in natures:
        db.session.execute(
            text(
                "INSERT OR IGNORE INTO project_natures (project_no, nature) "
                "VALUES (:project_no, :nature)"
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
                "INSERT OR IGNORE INTO project_personnel (project_no, personnel_id) "
                "VALUES (:project_no, :personnel_id)"
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
    page_query: ListPageQuery,
    load_all: bool = False,
) -> dict:
    keyword = keyword.strip().lower()
    where_clause, params = build_project_filters(keyword, status)

    total = db.session.execute(
        text(f"SELECT COUNT(*) AS total FROM projects p {where_clause}"),
        params,
    ).scalar_one()

    if load_all:
        rows = db.session.execute(
            text(f"SELECT p.* FROM projects p {where_clause} ORDER BY p.project_no ASC"),
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
        anchor_index = get_project_rank(where_clause, params, page_query.anchor)

    window = compute_paginated_window(
        total=total,
        page_size=page_query.page_size,
        page=None if page_query.anchor else page_query.page,
        anchor_index=anchor_index,
    )

    rows = db.session.execute(
        text(
            f"""
            SELECT p.* FROM projects p {where_clause}
            ORDER BY p.project_no ASC
            LIMIT :limit OFFSET :offset
            """
        ),
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
        return {"existing": []}
    placeholders = ", ".join(f":p{i}" for i in range(len(unique)))
    params = {f"p{i}": value for i, value in enumerate(unique)}
    rows = db.session.execute(
        text(f"SELECT project_no FROM projects WHERE project_no IN ({placeholders})"),
        params,
    ).all()
    return {"existing": [row.project_no for row in rows]}


def create_project(payload: dict) -> tuple[dict | None, str | None, int]:
    project_no = (payload.get("projectNo") or "").strip()
    if not project_no:
        return None, "项目号不能为空", 400
    if Project.query.get(project_no):
        return None, f"项目号 {project_no} 已存在", 409

    natures, nature_error = normalize_natures(payload.get("natures"))
    if nature_error:
        return None, nature_error, 400

    assignee_ids, assignee_error = normalize_assigned_personnel_ids(payload.get("assignedPersonnelIds"))
    if assignee_error:
        return None, assignee_error, 400

    name = (payload.get("name") or "").strip() or project_no
    status = (payload.get("status") or "").strip() or "active"
    contact_form_id = (payload.get("contactFormId") or "").strip()
    planned_start = (payload.get("plannedStartDate") or "").strip()
    received_date = planned_start or (get_contact_received_date(contact_form_id) if contact_form_id else "")

    project = Project(
        project_no=project_no,
        name=name,
        customer=format_customer_from_personnel_ids(assignee_ids or []),
        status=status,
        received_date=received_date,
        planned_start_date=planned_start,
        planned_end_date=(payload.get("plannedEndDate") or "").strip(),
        actual_start_date=(payload.get("actualStartDate") or "").strip(),
        actual_end_date=(payload.get("actualEndDate") or "").strip(),
        local_work_path=normalize_relative_path(payload.get("localWorkPath") or ""),
    )
    db.session.add(project)
    sync_project_natures(project_no, natures or [])
    sync_project_personnel(project_no, assignee_ids or [])

    if contact_form_id:
        exists = db.session.execute(
            text("SELECT id FROM contact_forms WHERE id = :id"),
            {"id": contact_form_id},
        ).first()
        if exists:
            db.session.execute(
                text(
                    "INSERT OR IGNORE INTO contact_form_projects "
                    "(contact_form_id, project_no) VALUES (:contact_form_id, :project_no)"
                ),
                {"contact_form_id": contact_form_id, "project_no": project_no},
            )

    db.session.commit()
    row = db.session.execute(
        text("SELECT * FROM projects WHERE project_no = :project_no"),
        {"project_no": project_no},
    ).first()
    return map_project(_row_to_dict(row)), None, 201


def update_project(project_no: str, payload: dict) -> tuple[dict | None, str | None, int]:
    row = db.session.execute(
        text("SELECT * FROM projects WHERE project_no = :project_no"),
        {"project_no": project_no},
    ).first()
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
    project.status = (payload.get("status") or "").strip() or existing["status"]
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
    project.local_work_path = (
        normalize_relative_path(payload.get("localWorkPath") or "")
        if payload.get("localWorkPath") is not None
        else normalize_relative_path(existing.get("local_work_path") or "")
    )

    sync_project_natures(project_no, natures or [])
    sync_project_personnel(project_no, assignee_ids or [])
    db.session.commit()

    updated = db.session.execute(
        text("SELECT * FROM projects WHERE project_no = :project_no"),
        {"project_no": project_no},
    ).first()
    return map_project(_row_to_dict(updated)), None, 200
