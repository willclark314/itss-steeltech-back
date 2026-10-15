"""SQLite → MySQL 数据同步（兼容封装，内部走双向 sync_databases）。"""

from __future__ import annotations

from typing import Callable

from sqlalchemy.engine import Engine

from steeltech_db.db_sync import sync_databases


def sync_to_mysql(
    source_engine: Engine,
    target_engine: Engine,
    *,
    dry_run: bool = False,
    log: Callable[[str], None] = print,
) -> dict:
    """执行 SQLite → MySQL 全量数据同步。"""
    result = sync_databases(
        source_engine,
        target_engine,
        dry_run=dry_run,
        mode="upsert",
        log=log,
    )
    return {
        "tables": result["tables"],
        "rows": result["rows"],
        "errors": result["errors"],
    }
