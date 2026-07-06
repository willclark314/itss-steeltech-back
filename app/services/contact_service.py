from __future__ import annotations

import base64
import hashlib
import uuid
from datetime import datetime
from pathlib import Path
import re

from sqlalchemy import text

from app.config import Config
from app.services import tag_service
from app.services.project_service import resolve_project_no
from steeltech_db.extensions import db
from steeltech_db.project_status import PROJECT_STATUS_CANCELLED
from app.utils.pagination import ListPageQuery, compute_paginated_window

FAMILY_MAX_RECEIVED_DATE = (
    "(SELECT MAX(family.received_date) FROM contact_forms family "
    "WHERE family.root_id = COALESCE(cf.root_id, cf.id) "
    "AND family.deleted_at IS NULL)"
)
CONTACT_LIST_ORDER = (
    f"{FAMILY_MAX_RECEIVED_DATE} DESC, "
    "COALESCE((SELECT MAX(cfp.project_no) FROM contact_form_projects cfp "
    "WHERE cfp.contact_form_id = cf.id), '') DESC, "
    "cf.sort_order ASC, cf.id ASC"
)
CONTACT_LIST_SELECT = f"cf.*, {FAMILY_MAX_RECEIVED_DATE} AS family_max_received_date"
CONTACT_PDF_ROOT = Path(Config.CONTACT_PDF_STORAGE_ROOT)
PROCESSING_CONTACT_ID = "加工单"
PROCESSING_CONTACT_ID_PREFIX = "加工单-"
PROCESSING_CONTACT_ID_PATTERN = re.compile(r"^BRD\d{6}C\d{9}$", re.IGNORECASE)


def _row_to_dict(row) -> dict:
    return dict(row._mapping)


def _now_local() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _generate_contact_id() -> str:
    now = datetime.now()
    prefix = f"DTP{now.strftime('%y%m%d')}"
    row = db.session.execute(
        text("SELECT COUNT(*) AS count FROM contact_forms WHERE id LIKE :prefix"),
        {"prefix": f"{prefix}%"},
    ).first()
    count = int(row.count) if row else 0
    return f"{prefix}{count + 1}"


def _is_processing_contact_id(contact_id: str) -> bool:
    normalized = (contact_id or "").strip()
    return (
        normalized == PROCESSING_CONTACT_ID
        or normalized.startswith(PROCESSING_CONTACT_ID_PREFIX)
        or bool(PROCESSING_CONTACT_ID_PATTERN.fullmatch(normalized))
    )


def _generate_processing_contact_id() -> str:
    return f"{PROCESSING_CONTACT_ID_PREFIX}{int(datetime.now().timestamp() * 1000)}_{uuid.uuid4().hex[:6]}"


def _generate_pdf_id() -> str:
    return f"pdf_{int(datetime.now().timestamp() * 1000)}_{uuid.uuid4().hex[:6]}"


def _generate_cancellation_id() -> str:
    return f"canc_{int(datetime.now().timestamp() * 1000)}_{uuid.uuid4().hex[:6]}"


def _normalize_pdf_relative_path(file_path: str) -> str:
    return file_path.replace("\\", "/")


def _has_pdf_payload(file: dict | None) -> bool:
    if not file:
        return False
    return bool(file.get("content") or str(file.get("md5", "")).strip())


def find_existing_pdf_by_md5(file_md5: str) -> dict | None:
    file_md5 = file_md5.strip().lower()
    if len(file_md5) != 32:
        return None

    row = db.session.execute(
        text(
            """
            SELECT file_path, file_size, file_name
            FROM contact_form_pdfs
            WHERE file_md5 = :file_md5
            ORDER BY created_at DESC
            LIMIT 1
            """
        ),
        {"file_md5": file_md5},
    ).first()
    if row and row.file_path:
        relative_path = _normalize_pdf_relative_path(row.file_path)
        abs_path = CONTACT_PDF_ROOT / Path(relative_path)
        if abs_path.is_file():
            return {
                "file_name": row.file_name,
                "file_path": relative_path,
                "file_md5": file_md5,
                "file_size": int(row.file_size or abs_path.stat().st_size),
                "deduplicated": True,
            }

    for abs_path in CONTACT_PDF_ROOT.rglob(f"{file_md5}.pdf"):
        if not abs_path.is_file():
            continue
        relative_path = abs_path.relative_to(CONTACT_PDF_ROOT).as_posix()
        return {
            "file_name": f"{file_md5}.pdf",
            "file_path": relative_path,
            "file_md5": file_md5,
            "file_size": abs_path.stat().st_size,
            "deduplicated": True,
        }
    return None


def check_pdf_md5(file_md5: str) -> dict:
    existing = find_existing_pdf_by_md5(file_md5)
    if not existing:
        return {"exists": False}
    return {
        "exists": True,
        "fileMd5": existing["file_md5"],
        "fileSize": existing["file_size"],
        "filePath": existing["file_path"],
    }


def _resolve_pdf_storage(
    *,
    file_name: str,
    content: str | None = None,
    md5: str | None = None,
) -> dict:
    file_md5 = str(md5 or "").strip().lower()
    content_bytes: bytes | None = None

    if content:
        content_bytes = base64.b64decode(content)
        computed_md5 = hashlib.md5(content_bytes).hexdigest()
        if file_md5 and file_md5 != computed_md5:
            raise ValueError("文件校验失败，请重新上传")
        file_md5 = computed_md5
    elif not file_md5:
        raise ValueError("请提供 PDF 文件内容或 MD5")

    existing = find_existing_pdf_by_md5(file_md5)
    if existing:
        return existing

    if content_bytes is None:
        raise ValueError("服务器未找到该文件，请重新上传完整文件")

    dated_path = datetime.now().strftime("%Y%m%d")
    target_dir = CONTACT_PDF_ROOT / dated_path
    target_dir.mkdir(parents=True, exist_ok=True)
    file_path = target_dir / f"{file_md5}.pdf"
    if not file_path.exists():
        file_path.write_bytes(content_bytes)
    relative_path = f"{dated_path}/{file_md5}.pdf"
    return {
        "file_name": f"{file_md5}.pdf",
        "file_path": relative_path,
        "file_md5": file_md5,
        "file_size": file_path.stat().st_size,
        "deduplicated": False,
    }


def _soft_delete_contact_pdfs(contact_form_id: str, deleted_at: str) -> None:
    db.session.execute(
        text(
            """
            UPDATE contact_form_pdfs
            SET deleted_at = :deleted_at
            WHERE contact_form_id = :contact_form_id AND deleted_at IS NULL
            """
        ),
        {"contact_form_id": contact_form_id, "deleted_at": deleted_at},
    )


def get_project_links_map(contact_form_ids: list[str]) -> dict[str, list[dict]]:
    if not contact_form_ids:
        return {}
    placeholders = ", ".join(f":c{i}" for i in range(len(contact_form_ids)))
    params = {f"c{i}": value for i, value in enumerate(contact_form_ids)}
    rows = db.session.execute(
        text(
            f"""
            SELECT contact_form_id, project_no, source_type, source_contact_form_id
            FROM contact_form_projects
            WHERE contact_form_id IN ({placeholders})
            ORDER BY project_no
            """
        ),
        params,
    ).all()
    result: dict[str, list[dict]] = {}
    for row in rows:
        result.setdefault(row.contact_form_id, []).append(
            {
                "projectNo": row.project_no,
                "sourceType": row.source_type,
                "sourceContactFormId": row.source_contact_form_id or None,
            }
        )
    return result


def get_pdfs_map(contact_form_ids: list[str]) -> tuple[dict[str, dict], dict[str, list[dict]], dict[str, list[dict]]]:
    if not contact_form_ids:
        return {}, {}, {}
    placeholders = ", ".join(f":c{i}" for i in range(len(contact_form_ids)))
    params = {f"c{i}": value for i, value in enumerate(contact_form_ids)}
    rows = db.session.execute(
        text(
            f"""
            SELECT contact_form_id, id, file_name, file_path, attachment_type,
                   created_at, is_current, original_file_name
            FROM contact_form_pdfs
            WHERE contact_form_id IN ({placeholders})
              AND deleted_at IS NULL
            ORDER BY sort_order, created_at
            """
        ),
        params,
    ).all()
    primary_map: dict[str, dict] = {}
    primary_versions_map: dict[str, list[dict]] = {}
    supplement_map: dict[str, list[dict]] = {}
    for row in rows:
        item = {
            "id": row.id,
            "name": row.original_file_name or row.file_name,
            "url": f"/api/contact-pdfs/{(row.file_path or '').replace(chr(92), '/')}",
            "createdAt": row.created_at,
            "isCurrent": bool(row.is_current),
        }
        if row.attachment_type == "primary":
            primary_versions_map.setdefault(row.contact_form_id, []).append(item)
            continue
        supplement_map.setdefault(row.contact_form_id, []).append(item)

    for contact_id, versions in primary_versions_map.items():
        versions.sort(key=lambda entry: entry["createdAt"], reverse=True)
        for index, entry in enumerate(versions):
            entry["version"] = len(versions) - index
        current = next((entry for entry in versions if entry.get("isCurrent")), versions[0])
        primary_map[contact_id] = current

    return primary_map, supplement_map, primary_versions_map


def get_child_count_map(root_ids: list[str]) -> dict[str, int]:
    if not root_ids:
        return {}
    placeholders = ", ".join(f":r{i}" for i in range(len(root_ids)))
    params = {f"r{i}": value for i, value in enumerate(root_ids)}
    rows = db.session.execute(
        text(
            f"""
            SELECT root_id, COUNT(*) AS total
            FROM contact_forms
            WHERE root_id IN ({placeholders})
              AND deleted_at IS NULL
            GROUP BY root_id
            """
        ),
        params,
    ).all()
    return {row.root_id: max(0, int(row.total) - 1) for row in rows}


def map_contact(
    row: dict,
    project_links_map: dict[str, list[dict]],
    primary_map: dict[str, dict],
    supplement_map: dict[str, list[dict]],
    primary_versions_map: dict[str, list[dict]],
    child_count_map: dict[str, int],
    tags_map: dict[str, list[dict]] | None = None,
) -> dict:
    contact_id = row["id"]
    project_links = project_links_map.get(contact_id, [])
    return {
        "id": contact_id,
        "title": row["title"],
        "projectNos": [item["projectNo"] for item in project_links],
        "projectLinks": project_links,
        "tags": (tags_map or {}).get(contact_id, []),
        "receivedDate": row["received_date"],
        "familyMaxReceivedDate": row.get("family_max_received_date") or row["received_date"],
        "urgency": row["urgency"],
        "status": row["status"],
        "content": row.get("content") or "",
        "parentId": row.get("parent_id") or None,
        "rootId": row.get("root_id") or contact_id,
        "relationType": row.get("relation_type") or "primary",
        "sortOrder": row.get("sort_order") or 0,
        "childCount": child_count_map.get(row.get("root_id") or contact_id, 0),
        "cancelScope": row.get("cancel_scope") or None,
        "primaryPdf": primary_map.get(contact_id),
        "primaryPdfVersions": primary_versions_map.get(contact_id, []),
        "attachments": supplement_map.get(contact_id, []),
        "createdAt": row["created_at"],
    }


def get_contact_by_id(contact_id: str) -> dict | None:
    row = db.session.execute(
        text(
            f"""
            SELECT {CONTACT_LIST_SELECT}
            FROM contact_forms cf
            WHERE cf.id = :id AND cf.deleted_at IS NULL
            """
        ),
        {"id": contact_id},
    ).first()
    if not row:
        return None
    contact_row = _row_to_dict(row)
    project_links_map = get_project_links_map([contact_id])
    primary_map, supplement_map, primary_versions_map = get_pdfs_map([contact_id])
    child_count_map = get_child_count_map([contact_row.get("root_id") or contact_id])
    tags_map = tag_service.get_contact_tags_map([contact_id])
    return map_contact(
        contact_row, project_links_map, primary_map, supplement_map, primary_versions_map, child_count_map, tags_map
    )


def build_contact_filters(
    keyword: str,
    status: str,
    assigned_personnel_id: str = "",
    tag_ids: list[str] | None = None,
) -> tuple[str, dict]:
    conditions: list[str] = ["cf.deleted_at IS NULL"]
    params: dict = {}

    personnel_id = (assigned_personnel_id or "").strip()
    if personnel_id:
        conditions.append(
            """EXISTS (
              SELECT 1 FROM contact_form_projects cfp
              INNER JOIN project_personnel pp ON pp.project_no = cfp.project_no
              WHERE cfp.contact_form_id = cf.id AND pp.personnel_id = :assigned_personnel_id
            )"""
        )
        params["assigned_personnel_id"] = personnel_id

    tag_clause, tag_params = tag_service.build_tag_exists_clause(
        entity_id_column="cf.id",
        join_table="contact_form_tags",
        join_entity_column="contact_form_id",
        tag_ids=tag_ids or [],
        param_prefix="contact_filter_tag",
    )
    if tag_clause:
        conditions.append(tag_clause)
        params.update(tag_params)

    if status:
        conditions.append("cf.status = :status")
        params["status"] = status

    if keyword:
        conditions.append(
            """(
              LOWER(cf.id) LIKE :kw
              OR LOWER(cf.title) LIKE :kw
              OR LOWER(cf.received_date) LIKE :kw
              OR EXISTS (
                SELECT 1
                FROM contact_form_projects cfp
                WHERE cfp.contact_form_id = cf.id AND LOWER(cfp.project_no) LIKE :kw
              )
              OR EXISTS (
                SELECT 1 FROM contact_form_tags cft
                INNER JOIN tags t ON t.id = cft.tag_id
                WHERE cft.contact_form_id = cf.id AND LOWER(t.name) LIKE :kw
              )
            )"""
        )
        params["kw"] = f"%{keyword}%"

    where_clause = f"WHERE {' AND '.join(conditions)}"
    return where_clause, params


def get_contact_rank(where_clause: str, params: dict, contact_id: str) -> int | None:
    row = db.session.execute(
        text(
            f"""
            WITH ranked AS (
              SELECT cf.id, ROW_NUMBER() OVER (ORDER BY {CONTACT_LIST_ORDER}) - 1 AS rank
              FROM contact_forms cf
              {where_clause}
            )
            SELECT rank FROM ranked WHERE id = :contact_id
            """
        ),
        {**params, "contact_id": contact_id},
    ).first()
    return int(row.rank) if row else None


def list_contacts(
    *,
    keyword: str = "",
    status: str = "",
    assigned_personnel_id: str = "",
    tag_ids: list[str] | None = None,
    page_query: ListPageQuery,
    load_all: bool = False,
) -> dict:
    keyword = keyword.strip().lower()
    where_clause, params = build_contact_filters(keyword, status, assigned_personnel_id, tag_ids)

    total = db.session.execute(
        text(f"SELECT COUNT(*) AS total FROM contact_forms cf {where_clause}"),
        params,
    ).scalar_one()

    if load_all:
        rows = db.session.execute(
            text(
                f"""
                SELECT {CONTACT_LIST_SELECT}
                FROM contact_forms cf
                {where_clause}
                ORDER BY {CONTACT_LIST_ORDER}
                """
            ),
            params,
        ).all()
        contact_rows = [_row_to_dict(row) for row in rows]
        contact_ids = [row["id"] for row in contact_rows]
        root_ids = list({row.get("root_id") or row["id"] for row in contact_rows})
        project_links_map = get_project_links_map(contact_ids)
        primary_map, supplement_map, primary_versions_map = get_pdfs_map(contact_ids)
        child_count_map = get_child_count_map(root_ids)
        tags_map = tag_service.get_contact_tags_map(contact_ids)
        items = [
            map_contact(
                row,
                project_links_map,
                primary_map,
                supplement_map,
                primary_versions_map,
                child_count_map,
                tags_map,
            )
            for row in contact_rows
        ]
        return {
            "list": items,
            "total": total,
            "page": 1,
            "pageSize": len(items),
            "totalPages": 1,
        }

    anchor_index = None
    if page_query.anchor:
        anchor_index = get_contact_rank(where_clause, params, page_query.anchor)

    window = compute_paginated_window(
        total=total,
        page_size=page_query.page_size,
        page=None if page_query.anchor else page_query.page,
        anchor_index=anchor_index,
    )

    rows = db.session.execute(
        text(
            f"""
            SELECT {CONTACT_LIST_SELECT}
            FROM contact_forms cf
            {where_clause}
            ORDER BY {CONTACT_LIST_ORDER}
            LIMIT :limit OFFSET :offset
            """
        ),
        {**params, "limit": window.limit, "offset": window.offset},
    ).all()

    contact_rows = [_row_to_dict(row) for row in rows]
    contact_ids = [row["id"] for row in contact_rows]
    root_ids = list({row.get("root_id") or row["id"] for row in contact_rows})
    project_links_map = get_project_links_map(contact_ids)
    primary_map, supplement_map, primary_versions_map = get_pdfs_map(contact_ids)
    child_count_map = get_child_count_map(root_ids)
    tags_map = tag_service.get_contact_tags_map(contact_ids)
    items = [
        map_contact(
            row,
            project_links_map,
            primary_map,
            supplement_map,
            primary_versions_map,
            child_count_map,
            tags_map,
        )
        for row in contact_rows
    ]

    return {
        "list": items,
        "total": total,
        "page": window.page,
        "pageSize": page_query.page_size,
        "totalPages": window.total_pages,
    }


def _insert_project_links(contact_form_id: str, links: list[dict]) -> None:
    for link in links:
        resolved_project_no = resolve_project_no(link["projectNo"])
        db.session.execute(
            text(
                """
                INSERT OR IGNORE INTO contact_form_projects (
                  contact_form_id, project_no, source_type, source_contact_form_id
                ) VALUES (:contact_form_id, :project_no, :source_type, :source_contact_form_id)
                """
            ),
            {
                "contact_form_id": contact_form_id,
                "project_no": resolved_project_no,
                "source_type": link["sourceType"],
                "source_contact_form_id": link.get("sourceContactFormId"),
            },
        )


def _insert_pdf_records(
    contact_form_id: str,
    primary_pdf: dict | None = None,
    supplement_files: list[dict] | None = None,
    created_at: str | None = None,
) -> None:
    created_at = created_at or _now_local()
    supplement_files = supplement_files or []

    if primary_pdf and _has_pdf_payload(primary_pdf):
        saved = _resolve_pdf_storage(
            file_name=str(primary_pdf.get("fileName") or ""),
            content=primary_pdf.get("content"),
            md5=primary_pdf.get("md5"),
        )
        db.session.execute(
            text(
                """
                INSERT INTO contact_form_pdfs (
                  id, contact_form_id, file_name, file_path, file_md5, file_size, mime_type,
                  attachment_type, sort_order, is_current, original_file_name, created_at
                ) VALUES (
                  :id, :contact_form_id, :file_name, :file_path, :file_md5, :file_size, :mime_type,
                  'primary', 0, 1, :original_file_name, :created_at
                )
                """
            ),
            {
                "id": _generate_pdf_id(),
                "contact_form_id": contact_form_id,
                "file_name": saved["file_name"],
                "file_path": saved["file_path"],
                "file_md5": saved["file_md5"],
                "file_size": saved["file_size"],
                "mime_type": "application/pdf",
                "original_file_name": primary_pdf.get("fileName") or saved["file_name"],
                "created_at": created_at,
            },
        )

    max_sort_row = db.session.execute(
        text(
            """
            SELECT COALESCE(MAX(sort_order), 0) AS max_sort
            FROM contact_form_pdfs
            WHERE contact_form_id = :contact_form_id AND attachment_type = 'supplement'
              AND deleted_at IS NULL
            """
        ),
        {"contact_form_id": contact_form_id},
    ).first()
    max_sort = int(max_sort_row.max_sort) if max_sort_row else 0

    for index, file in enumerate(supplement_files):
        if not _has_pdf_payload(file):
            continue
        saved = _resolve_pdf_storage(
            file_name=str(file.get("fileName") or ""),
            content=file.get("content"),
            md5=file.get("md5"),
        )
        db.session.execute(
            text(
                """
                INSERT INTO contact_form_pdfs (
                  id, contact_form_id, file_name, file_path, file_md5, file_size, mime_type,
                  attachment_type, sort_order, is_current, original_file_name, created_at
                ) VALUES (
                  :id, :contact_form_id, :file_name, :file_path, :file_md5, :file_size, :mime_type,
                  'supplement', :sort_order, 1, :original_file_name, :created_at
                )
                """
            ),
            {
                "id": _generate_pdf_id(),
                "contact_form_id": contact_form_id,
                "file_name": saved["file_name"],
                "file_path": saved["file_path"],
                "file_md5": saved["file_md5"],
                "file_size": saved["file_size"],
                "mime_type": "application/pdf",
                "sort_order": max_sort + index + 1,
                "original_file_name": file.get("fileName") or saved["file_name"],
                "created_at": created_at,
            },
        )


def _append_primary_pdf_version(
    contact_form_id: str,
    primary_pdf: dict,
    created_at: str | None = None,
) -> None:
    if not _has_pdf_payload(primary_pdf):
        return

    created_at = created_at or _now_local()
    saved = _resolve_pdf_storage(
        file_name=str(primary_pdf.get("fileName") or ""),
        content=primary_pdf.get("content"),
        md5=primary_pdf.get("md5"),
    )
    db.session.execute(
        text(
            """
            UPDATE contact_form_pdfs
            SET is_current = 0
            WHERE contact_form_id = :contact_form_id AND attachment_type = 'primary'
              AND deleted_at IS NULL
            """
        ),
        {"contact_form_id": contact_form_id},
    )
    db.session.execute(
        text(
            """
            INSERT INTO contact_form_pdfs (
              id, contact_form_id, file_name, file_path, file_md5, file_size, mime_type,
              attachment_type, sort_order, is_current, original_file_name, created_at
            ) VALUES (
              :id, :contact_form_id, :file_name, :file_path, :file_md5, :file_size, :mime_type,
              'primary', 0, 1, :original_file_name, :created_at
            )
            """
        ),
        {
            "id": _generate_pdf_id(),
            "contact_form_id": contact_form_id,
            "file_name": saved["file_name"],
            "file_path": saved["file_path"],
            "file_md5": saved["file_md5"],
            "file_size": saved["file_size"],
            "mime_type": "application/pdf",
            "original_file_name": primary_pdf.get("fileName") or saved["file_name"],
            "created_at": created_at,
        },
    )


def create_contact(payload: dict) -> dict:
    requested_id = str(payload.get("id", "")).strip()
    if requested_id:
        if _is_processing_contact_id(requested_id):
            contact_id = _generate_processing_contact_id()
        else:
            existing = db.session.execute(
                text("SELECT id FROM contact_forms WHERE id = :id"),
                {"id": requested_id},
            ).first()
            if existing:
                raise ValueError(f"联系单号 {requested_id} 已存在")
            contact_id = requested_id
    else:
        contact_id = _generate_contact_id()
    created_at = _now_local()
    db.session.execute(
        text(
            """
            INSERT INTO contact_forms (
              id, title, received_date, urgency, status, content, expect_reply_date,
              parent_id, root_id, relation_type, sort_order, created_at, updated_at
            ) VALUES (
              :id, :title, :received_date, :urgency, 'pending', :content, '',
              NULL, :root_id, 'primary', 0, :created_at, :updated_at
            )
            """
        ),
        {
            "id": contact_id,
            "title": payload["title"],
            "received_date": payload["receivedDate"],
            "urgency": payload.get("urgency") or "普通",
            "content": payload.get("content") or "",
            "root_id": contact_id,
            "created_at": created_at,
            "updated_at": created_at,
        },
    )
    links = [{"projectNo": no, "sourceType": "own"} for no in payload.get("projectNos") or []]
    _insert_project_links(contact_id, links)
    if "tagIds" in payload:
        tag_ids, tag_error = tag_service.normalize_tag_ids(payload.get("tagIds"))
        if tag_error:
            raise ValueError(tag_error)
        tag_service.sync_contact_tags(contact_id, tag_ids)
    _insert_pdf_records(contact_id, payload.get("primaryPdf"), payload.get("supplementFiles"), created_at)
    db.session.commit()
    return get_contact_by_id(contact_id)


def _rename_contact_id(old_id: str, new_id: str) -> None:
    ref_updates = [
        ("contact_form_projects", "contact_form_id"),
        ("contact_form_projects", "source_contact_form_id"),
        ("contact_form_pdfs", "contact_form_id"),
        ("contact_form_tags", "contact_form_id"),
        ("contact_form_project_cancellations", "cancel_contact_id"),
        ("contact_form_project_cancellations", "target_contact_id"),
        ("contact_forms", "parent_id"),
        ("contact_forms", "root_id"),
    ]
    db.session.execute(text("PRAGMA foreign_keys = OFF"))
    for table, column in ref_updates:
        db.session.execute(
            text(f"UPDATE {table} SET {column} = :new_id WHERE {column} = :old_id"),
            {"old_id": old_id, "new_id": new_id},
        )
    db.session.execute(
        text("UPDATE contact_forms SET id = :new_id WHERE id = :old_id"),
        {"old_id": old_id, "new_id": new_id},
    )
    db.session.execute(text("PRAGMA foreign_keys = ON"))


def update_contact(contact_id: str, payload: dict) -> dict | None:
    existing = db.session.execute(
        text("SELECT id FROM contact_forms WHERE id = :id AND deleted_at IS NULL"),
        {"id": contact_id},
    ).first()
    if not existing:
        return None

    if "id" in payload:
        new_id = str(payload.get("id", "")).strip()
        if not new_id:
            raise ValueError("联系单号不能为空")
        if _is_processing_contact_id(new_id):
            new_id = contact_id if _is_processing_contact_id(contact_id) else _generate_processing_contact_id()
        if new_id != contact_id:
            conflict = db.session.execute(
                text("SELECT id FROM contact_forms WHERE id = :id"),
                {"id": new_id},
            ).first()
            if conflict:
                raise ValueError(f"联系单号 {new_id} 已存在")
            _rename_contact_id(contact_id, new_id)
            contact_id = new_id

    fields = []
    params: dict = {"id": contact_id, "updated_at": _now_local()}
    mapping = {
        "title": "title",
        "receivedDate": "received_date",
        "urgency": "urgency",
        "content": "content",
        "status": "status",
    }
    for key, column in mapping.items():
        if key in payload:
            fields.append(f"{column} = :{column}")
            params[column] = payload[key]

    if fields:
        fields.append("updated_at = :updated_at")
        db.session.execute(
            text(f"UPDATE contact_forms SET {', '.join(fields)} WHERE id = :id"),
            params,
        )

    if "projectNos" in payload:
        db.session.execute(
            text("DELETE FROM contact_form_projects WHERE contact_form_id = :id"),
            {"id": contact_id},
        )
        links = [{"projectNo": no, "sourceType": "own"} for no in payload["projectNos"]]
        _insert_project_links(contact_id, links)

    if "tagIds" in payload:
        tag_ids, tag_error = tag_service.normalize_tag_ids(payload.get("tagIds"))
        if tag_error:
            raise ValueError(tag_error)
        tag_service.sync_contact_tags(contact_id, tag_ids)

    if payload.get("primaryPdf"):
        _append_primary_pdf_version(contact_id, payload["primaryPdf"])

    db.session.commit()
    return get_contact_by_id(contact_id)


def append_supplement_attachments(contact_id: str, files: list[dict]) -> dict | None:
    existing = db.session.execute(
        text("SELECT id FROM contact_forms WHERE id = :id AND deleted_at IS NULL"),
        {"id": contact_id},
    ).first()
    if not existing:
        return None
    _insert_pdf_records(contact_id, supplement_files=files)
    db.session.commit()
    return get_contact_by_id(contact_id)


def _get_parent_project_links(parent_id: str) -> list[dict]:
    rows = db.session.execute(
        text(
            """
            SELECT project_no, source_type, source_contact_form_id
            FROM contact_form_projects
            WHERE contact_form_id = :parent_id
            ORDER BY project_no
            """
        ),
        {"parent_id": parent_id},
    ).all()
    return [
        {
            "projectNo": row.project_no,
            "sourceType": "inherited",
            "sourceContactFormId": parent_id,
        }
        for row in rows
        if row.source_type != "cancelled"
    ]


def _build_child_project_links(
    parent_links: list[dict],
    project_mode: str,
    project_nos: list[str],
    relation_type: str,
    cancelled_project_nos: list[str],
) -> list[dict]:
    if relation_type == "cancel":
        return [{"projectNo": no, "sourceType": "cancelled"} for no in cancelled_project_nos]

    parent_active = [item for item in parent_links if item.get("sourceType") != "cancelled"]

    if project_mode == "inherit":
        return [
            {
                "projectNo": item["projectNo"],
                "sourceType": "inherited",
                "sourceContactFormId": item.get("sourceContactFormId"),
            }
            for item in parent_active
        ]

    if project_mode == "split":
        selected = set(project_nos)
        return [
            {
                "projectNo": item["projectNo"],
                "sourceType": "inherited",
                "sourceContactFormId": item.get("sourceContactFormId"),
            }
            for item in parent_active
            if item["projectNo"] in selected
        ]

    added = set(project_nos)
    inherited = [
        {
            "projectNo": item["projectNo"],
            "sourceType": "inherited",
            "sourceContactFormId": item.get("sourceContactFormId"),
        }
        for item in parent_active
    ]
    appended = [
        {"projectNo": project_no, "sourceType": "added"}
        for project_no in added
        if project_no not in {item["projectNo"] for item in parent_active}
    ]
    return inherited + appended


def _apply_cancel_effects(
    cancel_contact_id: str,
    target_contact_id: str,
    cancel_scope: str,
    cancelled_project_nos: list[str],
) -> None:
    target = db.session.execute(
        text("SELECT root_id FROM contact_forms WHERE id = :id"),
        {"id": target_contact_id},
    ).first()
    if not target:
        return

    root_id = target.root_id
    cancelled_at = _now_local()

    if cancel_scope == "full":
        rows = db.session.execute(
            text("SELECT id FROM contact_forms WHERE root_id = :root_id"),
            {"root_id": root_id},
        ).all()
        for row in rows:
            if row.id == cancel_contact_id:
                continue
            db.session.execute(
                text("UPDATE contact_forms SET status = 'cancelled', updated_at = :updated_at WHERE id = :id"),
                {"id": row.id, "updated_at": cancelled_at},
            )
        return

    for project_no in cancelled_project_nos:
        db.session.execute(
            text(
                """
                INSERT INTO contact_form_project_cancellations (
                  id, cancel_contact_id, target_contact_id, project_no, cancelled_at
                ) VALUES (:id, :cancel_contact_id, :target_contact_id, :project_no, :cancelled_at)
                """
            ),
            {
                "id": _generate_cancellation_id(),
                "cancel_contact_id": cancel_contact_id,
                "target_contact_id": target_contact_id,
                "project_no": project_no,
                "cancelled_at": cancelled_at,
            },
        )
        db.session.execute(
            text(
                """
                UPDATE projects
                SET status = :status, updated_at = :updated_at
                WHERE project_no = :project_no
                """
            ),
            {
                "project_no": project_no,
                "status": PROJECT_STATUS_CANCELLED,
                "updated_at": cancelled_at,
            },
        )
        linked = db.session.execute(
            text("SELECT contact_form_id FROM contact_form_projects WHERE project_no = :project_no"),
            {"project_no": project_no},
        ).all()
        for item in linked:
            contact = db.session.execute(
                text("SELECT root_id FROM contact_forms WHERE id = :id"),
                {"id": item.contact_form_id},
            ).first()
            if contact and contact.root_id == root_id:
                db.session.execute(
                    text(
                        "DELETE FROM contact_form_projects WHERE contact_form_id = :contact_form_id AND project_no = :project_no"
                    ),
                    {"contact_form_id": item.contact_form_id, "project_no": project_no},
                )

    remaining = db.session.execute(
        text("SELECT COUNT(*) AS count FROM contact_form_projects WHERE contact_form_id = :id"),
        {"id": target_contact_id},
    ).scalar_one()
    if remaining == 0:
        db.session.execute(
            text("UPDATE contact_forms SET status = 'cancelled', updated_at = :updated_at WHERE id = :id"),
            {"id": target_contact_id, "updated_at": cancelled_at},
        )


def create_child_contact(parent_id: str, payload: dict) -> dict | None:
    parent = db.session.execute(
        text("SELECT * FROM contact_forms WHERE id = :id AND deleted_at IS NULL"),
        {"id": parent_id},
    ).first()
    if not parent:
        return None

    parent_row = _row_to_dict(parent)
    max_sort_row = db.session.execute(
        text(
            "SELECT COALESCE(MAX(sort_order), 0) AS max_sort "
            "FROM contact_forms WHERE root_id = :root_id AND deleted_at IS NULL"
        ),
        {"root_id": parent_row["root_id"]},
    ).first()
    max_sort = int(max_sort_row.max_sort) if max_sort_row else 0

    contact_id = _generate_contact_id()
    created_at = _now_local()
    relation_type = payload.get("relationType") or "supplement"
    status = "done" if relation_type == "cancel" else "pending"

    db.session.execute(
        text(
            """
            INSERT INTO contact_forms (
              id, title, received_date, urgency, status, content, expect_reply_date,
              parent_id, root_id, relation_type, sort_order, cancel_scope, created_at, updated_at
            ) VALUES (
              :id, :title, :received_date, :urgency, :status, :content, '',
              :parent_id, :root_id, :relation_type, :sort_order, :cancel_scope, :created_at, :updated_at
            )
            """
        ),
        {
            "id": contact_id,
            "title": payload["title"],
            "received_date": payload["receivedDate"],
            "urgency": payload.get("urgency") or parent_row.get("urgency") or "普通",
            "status": status,
            "content": payload.get("content") or "",
            "parent_id": parent_id,
            "root_id": parent_row["root_id"],
            "relation_type": relation_type,
            "sort_order": max_sort + 1,
            "cancel_scope": payload.get("cancelScope") if relation_type == "cancel" else None,
            "created_at": created_at,
            "updated_at": created_at,
        },
    )

    parent_links = _get_parent_project_links(parent_id)
    project_links = _build_child_project_links(
        parent_links,
        payload.get("projectMode") or "inherit",
        payload.get("projectNos") or [],
        relation_type,
        payload.get("cancelledProjectNos") or [],
    )
    _insert_project_links(contact_id, project_links)
    _insert_pdf_records(contact_id, payload.get("primaryPdf"), payload.get("supplementFiles"), created_at)

    if relation_type == "cancel":
        _apply_cancel_effects(
            contact_id,
            parent_row["root_id"],
            payload.get("cancelScope") or "partial",
            payload.get("cancelledProjectNos") or [item["projectNo"] for item in project_links],
        )

    db.session.commit()
    return get_contact_by_id(contact_id)


def delete_contact(contact_id: str) -> bool:
    existing = db.session.execute(
        text("SELECT id FROM contact_forms WHERE id = :id AND deleted_at IS NULL"),
        {"id": contact_id},
    ).first()
    if not existing:
        return False

    deleted_at = _now_local()
    _soft_delete_contact_pdfs(contact_id, deleted_at)
    db.session.execute(
        text(
            """
            UPDATE contact_forms
            SET deleted_at = :deleted_at, updated_at = :updated_at
            WHERE id = :id
            """
        ),
        {"id": contact_id, "deleted_at": deleted_at, "updated_at": deleted_at},
    )
    db.session.commit()
    return True
