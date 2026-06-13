from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass
class ListPageQuery:
    page_size: int
    page: int
    anchor: str | None = None


@dataclass
class PaginatedWindow:
    offset: int
    limit: int
    page: int
    total_pages: int


def parse_list_page_query(args, *, default_page_size: int = 20) -> ListPageQuery:
    try:
        page_size = int(args.get("pageSize", default_page_size))
    except (TypeError, ValueError):
        page_size = default_page_size
    page_size = max(1, min(100, page_size))

    try:
        page = int(args.get("page", 1))
    except (TypeError, ValueError):
        page = 1
    page = max(1, page)

    anchor = (args.get("anchor") or "").strip() or None
    return ListPageQuery(page_size=page_size, page=page, anchor=anchor)


def compute_paginated_window(
    *,
    total: int,
    page_size: int,
    page: int | None = None,
    anchor_index: int | None = None,
) -> PaginatedWindow:
    total_pages = math.ceil(total / page_size) if total > 0 else 1

    resolved_page = page or 1
    if anchor_index is not None and anchor_index >= 0:
        resolved_page = anchor_index // page_size + 1

    resolved_page = max(1, min(resolved_page, total_pages))

    if total <= 0:
        return PaginatedWindow(offset=0, limit=0, page=1, total_pages=1)

    offset = (resolved_page - 1) * page_size
    limit = min(page_size, total - offset)
    return PaginatedWindow(
        offset=offset,
        limit=limit,
        page=resolved_page,
        total_pages=total_pages,
    )
