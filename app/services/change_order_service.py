from __future__ import annotations

import base64
import hashlib
import mimetypes
import re
import uuid
from datetime import datetime
from pathlib import Path

from sqlalchemy import text

from app.config import Config
from app.utils.pagination import ListPageQuery, compute_paginated_window
from app.utils.sql_helpers import insert_ignore
from steeltech_db.extensions import db
from steeltech_db.models.change_order import ChangeOrder


CHANGE_ORDER_LIST_ORDER = "co.received_date DESC, co.id DESC"
CHANGE_ORDER_LIST_SELECT = "co.*"
CHANGE_ORDER_PDF_ROOT = Path(Config.CHANGE_ORDER_PDF_STORAGE_ROOT)




def _row_to_dict(row) -> dict:
    if hasattr(row, "_mapping"):
        return dict(row._mapping)
    return {c.name: getattr(row, c.name) for c in row.__table__.columns}


def _now_local() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _generate_order_no() -> str:
    """生成默认变更单号 BG{年月日}{序号}"""
    now = datetime.now()
    prefix = f"BG{now.strftime('%y%m%d')}"
    row = db.session.execute(
        text("SELECT COUNT(*) AS count FROM change_orders WHERE order_no LIKE :prefix"),
        {"prefix": f"{prefix}%"},
    ).first()
    count = int(row.count) if row else 0
    return f"{prefix}{count + 1}"


def _generate_pdf_id() -> str:
    return f"bg_{int(datetime.now().timestamp() * 1000)}_{uuid.uuid4().hex[:6]}"


def _sanitize_extension(file_name: str) -> str:
    suffix = Path(file_name).suffix.lower()
    if suffix and re.fullmatch(r"\.[a-z0-9]{1,10}", suffix):
        return suffix
    return ""


def _guess_mime_type(file_name: str) -> str:
    mime_type, _ = mimetypes.guess_type(file_name)
    return mime_type or "application/octet-stream"


def _normalize_pdf_relative_path(file_path: str) -> str:
    return file_path.replace("\\", "/")


def _has_file_payload(file: dict | None) -> bool:
    if not file:
        return False
    return bool(file.get("content") or str(file.get("md5", "")).strip())


def _build_pdf_url(file_path: str) -> str:
    normalized = _normalize_pdf_relative_path(file_path)
    return f"/api/change-order-pdfs/{normalized}"


def _normalize_primary_files(payload: dict) -> list[dict]:
    """统一解析正文文件列表：优先 primaryFiles，兼容旧字段 primaryPdf / supplementFiles。"""
    files: list[dict] = []
    primary_files = payload.get("primaryFiles")
    if isinstance(primary_files, list):
        files.extend(item for item in primary_files if isinstance(item, dict))
    primary_pdf = payload.get("primaryPdf")
    if isinstance(primary_pdf, dict):
        files.append(primary_pdf)
    # 兼容旧客户端：supplementFiles 一并写入正文
    supplement_files = payload.get("supplementFiles")
    if isinstance(supplement_files, list):
        files.extend(item for item in supplement_files if isinstance(item, dict))
    return files


def find_existing_file_by_md5(file_md5: str) -> dict | None:
    file_md5 = file_md5.strip().lower()
    if len(file_md5) != 32:
        return None

    row = db.session.execute(
        text("""
            SELECT file_path, file_size, file_name, original_file_name, mime_type
            FROM change_order_pdfs
            WHERE file_md5 = :file_md5
            ORDER BY created_at DESC LIMIT 1
        """),
        {"file_md5": file_md5},
    ).first()
    if row and row.file_path:
        relative_path = _normalize_pdf_relative_path(row.file_path)
        abs_path = CHANGE_ORDER_PDF_ROOT / Path(relative_path)
        if abs_path.is_file():
            return {
                "file_name": row.file_name, "file_path": relative_path,
                "file_md5": file_md5, "file_size": int(row.file_size or abs_path.stat().st_size),
                "mime_type": row.mime_type or _guess_mime_type(row.original_file_name or row.file_name),
                "deduplicated": True,
            }
    for abs_path in CHANGE_ORDER_PDF_ROOT.rglob(f"{file_md5}.*"):
        if not abs_path.is_file():
            continue
        relative_path = abs_path.relative_to(CHANGE_ORDER_PDF_ROOT).as_posix()
        return {
            "file_name": abs_path.name, "file_path": relative_path,
            "file_md5": file_md5, "file_size": abs_path.stat().st_size,
            "mime_type": _guess_mime_type(abs_path.name), "deduplicated": True,
        }
    return None


def check_pdf_md5(file_md5: str) -> dict:
    existing = find_existing_file_by_md5(file_md5)
    if not existing:
        return {"exists": False}
    return {"exists": True, "fileMd5": existing["file_md5"], "fileSize": existing["file_size"], "filePath": existing["file_path"]}


def _resolve_file_storage(*, file_name: str, content: str | None = None, md5: str | None = None) -> dict:
    file_md5 = str(md5 or "").strip().lower()
    content_bytes: bytes | None = None
    if content:
        content_bytes = base64.b64decode(content)
        computed_md5 = hashlib.md5(content_bytes).hexdigest()
        if file_md5 and file_md5 != computed_md5:
            raise ValueError("文件校验失败，请重新上传")
        file_md5 = computed_md5
    elif not file_md5:
        raise ValueError("请提供文件内容或 MD5")
    existing = find_existing_file_by_md5(file_md5)
    if existing:
        return existing
    if content_bytes is None:
        raise ValueError("服务器未找到该文件，请重新上传完整文件")
    extension = _sanitize_extension(file_name) or ".bin"
    dated_path = datetime.now().strftime("%Y%m%d")
    target_dir = CHANGE_ORDER_PDF_ROOT / dated_path
    target_dir.mkdir(parents=True, exist_ok=True)
    stored_name = f"{file_md5}{extension}"
    file_path = target_dir / stored_name
    if not file_path.exists():
        file_path.write_bytes(content_bytes)
    relative_path = f"{dated_path}/{stored_name}"
    return {
        "file_name": stored_name,
        "file_path": relative_path,
        "file_md5": file_md5,
        "file_size": file_path.stat().st_size,
        "mime_type": _guess_mime_type(file_name),
        "deduplicated": False,
    }


def _insert_project_links(change_order_id,
project_nos: list[str]) -> None:
    for project_no in project_nos:
        raw = str(project_no).strip()
        if not raw:
            continue
        existing = db.session.execute(
            text("SELECT project_no FROM projects WHERE project_no = :no"), {"no": raw},
        ).first()
        if not existing:
            continue
        db.session.execute(
            text(insert_ignore("change_order_projects", "change_order_id, project_no") + " VALUES (:change_order_id, :project_no)"),
            {"change_order_id": change_order_id, "project_no": raw},
        )


def _insert_primary_files(change_order_id,
files: list[dict] | None = None, created_at: str | None = None) -> None:
    created_at = created_at or _now_local()
    files = files or []
    if not files:
        return

    max_sort_row = db.session.execute(
        text("""
            SELECT COALESCE(MAX(sort_order), 0) AS max_sort
            FROM change_order_pdfs
            WHERE change_order_id = :change_order_id
              AND attachment_type = 'primary'
              AND is_current = 1
              AND deleted_at IS NULL
        """),
        {"change_order_id": change_order_id},
    ).first()
    max_sort = int(max_sort_row.max_sort) if max_sort_row else 0

    for index, file in enumerate(files):
        if not _has_file_payload(file):
            continue
        saved = _resolve_file_storage(
            file_name=str(file.get("fileName") or ""),
            content=file.get("content"),
            md5=file.get("md5"),
        )
        db.session.execute(
            text("""INSERT INTO change_order_pdfs (
              id, change_order_id, file_name, file_path, file_md5, file_size, mime_type,
              attachment_type, sort_order, is_current, original_file_name, created_at
            ) VALUES (
              :id, :change_order_id, :file_name, :file_path, :file_md5, :file_size, :mime_type,
              'primary', :sort_order, 1, :original_file_name, :created_at
            )"""),
            {
                "id": _generate_pdf_id(),
                "change_order_id": change_order_id,
                "file_name": saved["file_name"],
                "file_path": saved["file_path"],
                "file_md5": saved["file_md5"],
                "file_size": saved["file_size"],
                "mime_type": saved.get("mime_type") or _guess_mime_type(str(file.get("fileName") or saved["file_name"])),
                "sort_order": max_sort + index + 1,
                "original_file_name": file.get("fileName") or saved["file_name"],
                "created_at": created_at,
            },
        )


def _soft_delete_primary_files(change_order_id,
file_ids: list[str], deleted_at: str | None = None) -> None:
    deleted_at = deleted_at or _now_local()
    for file_id in file_ids:
        normalized_id = (file_id or "").strip()
        if not normalized_id:
            continue
        db.session.execute(
            text("""
                UPDATE change_order_pdfs
                SET deleted_at = :deleted_at
                WHERE id = :id
                  AND change_order_id = :change_order_id
                  AND attachment_type = 'primary'
                  AND deleted_at IS NULL
            """),
            {"id": normalized_id, "change_order_id": change_order_id, "deleted_at": deleted_at},
        )


def get_project_nos_map(change_order_ids: list) -> dict:
    if not change_order_ids:
        return {}
    placeholders = ", ".join(f":c{i}" for i in range(len(change_order_ids)))
    params = {f"c{i}": value for i, value in enumerate(change_order_ids)}
    rows = db.session.execute(
        text(f"SELECT change_order_id, project_no FROM change_order_projects WHERE change_order_id IN ({placeholders}) ORDER BY project_no"),
        params,
    ).all()
    result: dict = {}
    for row in rows:
        result.setdefault(row.change_order_id, []).append(row.project_no)
    return result


def get_pdfs_map(change_order_ids: list) -> tuple[dict, dict]:
    if not change_order_ids:
        return {}, {}
    placeholders = ", ".join(f":c{i}" for i in range(len(change_order_ids)))
    params = {f"c{i}": value for i, value in enumerate(change_order_ids)}
    rows = db.session.execute(
        text(f"""
          SELECT change_order_id, id, file_name, file_path, created_at, is_current, original_file_name, sort_order
          FROM change_order_pdfs
          WHERE change_order_id IN ({placeholders})
            AND deleted_at IS NULL
            AND attachment_type = 'primary'
          ORDER BY sort_order, created_at
        """),
        params,
    ).all()
    primary_map: dict = {}
    primary_versions_map: dict = {}
    for row in rows:
        item = {
            "id": row.id,
            "name": row.original_file_name or row.file_name,
            "url": _build_pdf_url(row.file_path or ""),
            "createdAt": row.created_at,
            "isCurrent": bool(row.is_current),
        }
        cid = row.change_order_id
        primary_versions_map.setdefault(cid, []).append(item)
        if row.is_current:
            primary_map.setdefault(cid, []).append(item)

    for cid, versions in primary_versions_map.items():
        versions.sort(key=lambda e: e["createdAt"], reverse=True)
        for index, entry in enumerate(versions):
            entry["version"] = len(versions) - index

    return primary_map, primary_versions_map


def _map_change_order(row: dict, project_nos_map: dict, primary_map: dict, primary_versions_map: dict) -> dict:
    oid = row["id"]
    primary_pdfs = primary_map.get(oid, [])
    return {
        "id": oid,
        "orderNo": row.get("order_no") or "",
        "title": row["title"],
        "projectNos": project_nos_map.get(oid, []),
        "receivedDate": row["received_date"],
        "content": row.get("content") or "",
        "primaryPdfs": primary_pdfs,
        "primaryPdf": primary_pdfs[0] if primary_pdfs else None,
        "primaryPdfVersions": primary_versions_map.get(oid, []),
        "createdAt": row["created_at"],
    }


def get_change_order_by_id(change_order_id) -> dict | None:
    row = db.session.execute(
        text(f"SELECT {CHANGE_ORDER_LIST_SELECT} FROM change_orders co WHERE co.id = :id AND co.deleted_at IS NULL"),
        {"id": change_order_id},
    ).first()
    if not row:
        return None
    order_row = _row_to_dict(row)
    oid = order_row["id"]
    project_nos_map = get_project_nos_map([oid])
    primary_map, primary_versions_map = get_pdfs_map([oid])
    return _map_change_order(order_row, project_nos_map, primary_map, primary_versions_map)


def list_change_orders(*, keyword: str = "", page_query: ListPageQuery) -> dict:
    keyword = keyword.strip().lower()
    conditions: list[str] = ["co.deleted_at IS NULL"]
    params: dict = {}

    if keyword:
        conditions.append("""(
          LOWER(COALESCE(co.order_no, '')) LIKE :kw OR LOWER(co.title) LIKE :kw OR LOWER(co.received_date) LIKE :kw
          OR EXISTS (SELECT 1 FROM change_order_projects cop WHERE cop.change_order_id = co.id AND LOWER(cop.project_no) LIKE :kw)
        )""")
        params["kw"] = f"%{keyword}%"

    where_clause = f"WHERE {' AND '.join(conditions)}"
    total = db.session.execute(text(f"SELECT COUNT(*) AS total FROM change_orders co {where_clause}"), params).scalar_one()

    window = compute_paginated_window(total=total, page_size=page_query.page_size, page=page_query.page, anchor_index=None)

    rows = db.session.execute(
        text(f"SELECT {CHANGE_ORDER_LIST_SELECT} FROM change_orders co {where_clause} ORDER BY {CHANGE_ORDER_LIST_ORDER} LIMIT :limit OFFSET :offset"),
        {**params, "limit": window.limit, "offset": window.offset},
    ).all()

    order_rows = [_row_to_dict(row) for row in rows]
    order_ids = [row["id"] for row in order_rows]
    project_nos_map = get_project_nos_map(order_ids)
    primary_map, primary_versions_map = get_pdfs_map(order_ids)
    items = [_map_change_order(row, project_nos_map, primary_map, primary_versions_map) for row in order_rows]

    return {"list": items, "total": total, "page": window.page, "pageSize": page_query.page_size, "totalPages": window.total_pages}


def create_change_order(payload: dict) -> dict:
    order_no = str(payload.get("orderNo", "")).strip()
    if order_no:
        existing = ChangeOrder.query.filter_by(order_no=order_no, deleted_at=None).first()
        if existing:
            raise ValueError(f"变更单号 {order_no} 已存在")
    else:
        order_no = _generate_order_no()

    created_at = _now_local()
    db.session.execute(
        text("INSERT INTO change_orders (order_no, title, received_date, content, created_at, updated_at) VALUES (:order_no, :title, :received_date, :content, :created_at, :updated_at)"),
        {"order_no": order_no, "title": payload["title"], "received_date": payload.get("receivedDate") or "",
         "content": payload.get("content") or "", "created_at": created_at, "updated_at": created_at},
    )

    row = db.session.execute(
        text("SELECT id FROM change_orders WHERE order_no = :order_no AND created_at = :created_at"),
        {"order_no": order_no, "created_at": created_at},
    ).first()
    change_order_id = row.id if row else 0

    _insert_project_links(change_order_id, payload.get("projectNos") or [])
    _insert_primary_files(change_order_id, _normalize_primary_files(payload), created_at)
    db.session.commit()
    return get_change_order_by_id(change_order_id)


def update_change_order(change_order_id,
payload: dict) -> dict | None:
    existing = ChangeOrder.query.filter_by(id=change_order_id, deleted_at=None).first()
    if not existing:
        return None

    fields = []
    params: dict = {"id": change_order_id, "updated_at": _now_local()}
    if "orderNo" in payload:
        new_order_no = str(payload.get("orderNo", "")).strip()
        current_order_no = (existing.order_no or "").strip()
        if new_order_no != current_order_no:
            if new_order_no:
                conflict = ChangeOrder.query.filter_by(order_no=new_order_no, deleted_at=None).first()
                if conflict and conflict.id != change_order_id:
                    raise ValueError(f"变更单号 {new_order_no} 已存在")
                fields.append("order_no = :order_no")
                params["order_no"] = new_order_no
    for key, column in [("title", "title"), ("receivedDate", "received_date"), ("content", "content")]:
        if key in payload:
            fields.append(f"{column} = :{column}")
            params[column] = payload[key]

    if fields:
        fields.append("updated_at = :updated_at")
        db.session.execute(text(f"UPDATE change_orders SET {', '.join(fields)} WHERE id = :id"), params)

    if "projectNos" in payload:
        db.session.execute(text("DELETE FROM change_order_projects WHERE change_order_id = :id"), {"id": change_order_id})
        _insert_project_links(change_order_id, payload["projectNos"])

    removed_ids = payload.get("removedPrimaryIds") or payload.get("removedAttachmentIds") or []
    if removed_ids:
        _soft_delete_primary_files(change_order_id, removed_ids)

    primary_files = _normalize_primary_files(payload)
    if primary_files:
        _insert_primary_files(change_order_id, primary_files)

    db.session.commit()
    return get_change_order_by_id(change_order_id)


def delete_change_order(change_order_id) -> bool:
    existing = ChangeOrder.query.filter_by(id=change_order_id, deleted_at=None).first()
    if not existing:
        return False
    deleted_at = _now_local()
    existing.deleted_at = deleted_at
    db.session.execute(
        text("UPDATE change_order_pdfs SET deleted_at = :deleted_at WHERE change_order_id = :change_order_id AND deleted_at IS NULL"),
        {"change_order_id": change_order_id, "deleted_at": deleted_at},
    )
    db.session.commit()
    return True


def append_primary_files(change_order_id,
files: list[dict]) -> dict | None:
    existing = ChangeOrder.query.filter_by(id=change_order_id, deleted_at=None).first()
    if not existing:
        return None
    _insert_primary_files(change_order_id, files)
    db.session.commit()
    return get_change_order_by_id(change_order_id)
