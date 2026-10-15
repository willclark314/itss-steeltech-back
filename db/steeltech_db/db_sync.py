"""双向数据库同步（SQLite ↔ MySQL）。

按外键拓扑顺序全量同步表数据，支持 dry-run、upsert / replace，以及行数校验。
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any, Callable, Literal

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

SyncMode = Literal["upsert", "replace"]


def _dialect_name(engine: Engine) -> str:
    return engine.dialect.name


def _quote(name: str, dialect: str) -> str:
    if dialect == "mysql":
        return f"`{name}`"
    return f'"{name}"'


def _normalize_value(value: Any) -> Any:
    """写入前做轻量类型归一，降低 SQLite ↔ MySQL 差异导致的失败。"""
    if value is None:
        return None
    if isinstance(value, bool):
        return 1 if value else 0
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d %H:%M:%S")
    if isinstance(value, date):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, memoryview):
        return bytes(value)
    if isinstance(value, bytearray):
        return bytes(value)
    return value


def _normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    return {key: _normalize_value(value) for key, value in row.items()}


def _table_order(engine: Engine) -> list[str]:
    """按外键依赖排序表名（父表在前，子表在后）。"""
    inspector = inspect(engine)
    all_tables = inspector.get_table_names()

    skip = {"alembic_version"}
    tables = [t for t in all_tables if t not in skip and not t.startswith("sqlite_")]

    deps: dict[str, set[str]] = {}
    for table in tables:
        deps[table] = set()
        for fk in inspector.get_foreign_keys(table):
            referred = fk["referred_table"]
            if referred in tables and referred != table:
                deps[table].add(referred)

    in_degree: dict[str, int] = {t: len(deps[t]) for t in tables}
    queue = [t for t in tables if in_degree[t] == 0]
    ordered: list[str] = []

    while queue:
        node = queue.pop(0)
        ordered.append(node)
        for table in tables:
            if node in deps.get(table, set()):
                in_degree[table] -= 1
                if in_degree[table] == 0:
                    queue.append(table)

    remaining = [t for t in tables if t not in ordered]
    ordered.extend(remaining)
    return ordered


def _disable_fk_checks(engine: Engine) -> None:
    dialect = _dialect_name(engine)
    with engine.connect() as conn:
        if dialect == "mysql":
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        elif dialect == "sqlite":
            conn.execute(text("PRAGMA foreign_keys = OFF"))
        conn.commit()


def _enable_fk_checks(engine: Engine) -> None:
    dialect = _dialect_name(engine)
    with engine.connect() as conn:
        if dialect == "mysql":
            conn.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
        elif dialect == "sqlite":
            conn.execute(text("PRAGMA foreign_keys = ON"))
        conn.commit()


def _truncate_table(engine: Engine, table_name: str) -> None:
    dialect = _dialect_name(engine)
    q = _quote(table_name, dialect)
    with engine.connect() as conn:
        if dialect == "mysql":
            conn.execute(text(f"TRUNCATE TABLE {q}"))
        else:
            conn.execute(text(f"DELETE FROM {q}"))
        conn.commit()


def _build_upsert_sql(
    dialect: str,
    table_name: str,
    columns: list[str],
    pk_columns: list[str],
) -> str:
    q_table = _quote(table_name, dialect)
    col_names = ", ".join(_quote(col, dialect) for col in columns)
    placeholders = ", ".join(f":{col}" for col in columns)

    if dialect == "mysql":
        if pk_columns:
            non_pk = [col for col in columns if col not in pk_columns]
            if non_pk:
                update_parts = ", ".join(
                    f"{_quote(col, dialect)} = VALUES({_quote(col, dialect)})" for col in non_pk
                )
                return (
                    f"INSERT INTO {q_table} ({col_names}) VALUES ({placeholders}) "
                    f"ON DUPLICATE KEY UPDATE {update_parts}"
                )
            return f"INSERT IGNORE INTO {q_table} ({col_names}) VALUES ({placeholders})"
        return f"REPLACE INTO {q_table} ({col_names}) VALUES ({placeholders})"

    # SQLite
    if pk_columns:
        conflict = ", ".join(_quote(col, dialect) for col in pk_columns)
        non_pk = [col for col in columns if col not in pk_columns]
        if non_pk:
            update_parts = ", ".join(
                f"{_quote(col, dialect)} = excluded.{_quote(col, dialect)}" for col in non_pk
            )
            return (
                f"INSERT INTO {q_table} ({col_names}) VALUES ({placeholders}) "
                f"ON CONFLICT ({conflict}) DO UPDATE SET {update_parts}"
            )
        return (
            f"INSERT INTO {q_table} ({col_names}) VALUES ({placeholders}) "
            f"ON CONFLICT ({conflict}) DO NOTHING"
        )
    return f"INSERT OR REPLACE INTO {q_table} ({col_names}) VALUES ({placeholders})"


def _build_insert_sql(dialect: str, table_name: str, columns: list[str]) -> str:
    q_table = _quote(table_name, dialect)
    col_names = ", ".join(_quote(col, dialect) for col in columns)
    placeholders = ", ".join(f":{col}" for col in columns)
    return f"INSERT INTO {q_table} ({col_names}) VALUES ({placeholders})"


def _intersect_columns(
    source_engine: Engine,
    target_engine: Engine,
    table_name: str,
) -> tuple[list[str], list[str]]:
    """取源/目标共有列；主键以源表为准并过滤到共有列。"""
    src_inspector = inspect(source_engine)
    tgt_inspector = inspect(target_engine)

    src_cols = [col["name"] for col in src_inspector.get_columns(table_name)]
    tgt_cols = {col["name"] for col in tgt_inspector.get_columns(table_name)}
    columns = [col for col in src_cols if col in tgt_cols]

    pk = src_inspector.get_pk_constraint(table_name)
    pk_columns = [col for col in (pk["constrained_columns"] if pk else []) if col in columns]
    return columns, pk_columns


def _sync_table(
    source_engine: Engine,
    target_engine: Engine,
    table_name: str,
    *,
    mode: SyncMode = "upsert",
    dry_run: bool = False,
    log: Callable[[str], None] = print,
) -> int:
    target_dialect = _dialect_name(target_engine)
    src_dialect = _dialect_name(source_engine)
    q_table = _quote(table_name, src_dialect)

    if dry_run:
        # 预览只读源库，不要求目标已建表
        with source_engine.connect() as src_conn:
            count = src_conn.execute(text(f"SELECT COUNT(*) FROM {q_table}")).scalar() or 0
        count = int(count)
        if count == 0:
            log(f"  [跳过] {table_name}: 0 行")
            return 0
        log(f"  [预览] {table_name}: {count} 行")
        return count

    columns, pk_columns = _intersect_columns(source_engine, target_engine, table_name)

    if not columns:
        log(f"  [跳过] {table_name}: 无共有列")
        return 0

    with source_engine.connect() as src_conn:
        rows = [
            _normalize_row(dict(row))
            for row in src_conn.execute(text(f"SELECT * FROM {q_table}")).mappings().all()
        ]

    if not rows:
        log(f"  [跳过] {table_name}: 0 行")
        return 0

    if mode == "upsert":
        write_sql = _build_upsert_sql(target_dialect, table_name, columns, pk_columns)
    else:
        write_sql = _build_insert_sql(target_dialect, table_name, columns)

    with target_engine.connect() as tgt_conn:
        trans = tgt_conn.begin()
        try:
            for row in rows:
                payload = {col: row.get(col) for col in columns}
                tgt_conn.execute(text(write_sql), payload)
            trans.commit()
        except Exception:
            trans.rollback()
            raise

    return len(rows)


def sync_databases(
    source_engine: Engine,
    target_engine: Engine,
    *,
    dry_run: bool = False,
    mode: SyncMode = "upsert",
    log: Callable[[str], None] = print,
) -> dict:
    """执行双向全量数据同步。

    Returns:
        {"tables": int, "rows": int, "errors": int, "per_table": {name: count}}
    """
    if mode not in ("upsert", "replace"):
        raise ValueError(f"Unsupported sync mode: {mode}")

    ordered_tables = _table_order(source_engine)
    if not dry_run:
        target_tables = set(inspect(target_engine).get_table_names())
        ordered_tables = [t for t in ordered_tables if t in target_tables]

    log(f"同步模式: {mode}")
    log(f"同步顺序: {' → '.join(ordered_tables)}")
    if dry_run:
        log("[DRY RUN] 仅预览，不会实际写入\n")

    if not dry_run:
        _disable_fk_checks(target_engine)
        if mode == "replace":
            # 子表先清空（逆拓扑）
            for table_name in reversed(ordered_tables):
                try:
                    _truncate_table(target_engine, table_name)
                    log(f"  [清空] {table_name}")
                except Exception as exc:
                    log(f"  [清空失败] {table_name}: {exc}")

    total_rows = 0
    total_tables = 0
    errors = 0
    per_table: dict[str, int] = {}

    try:
        for table_name in ordered_tables:
            try:
                rows = _sync_table(
                    source_engine,
                    target_engine,
                    table_name,
                    mode=mode,
                    dry_run=dry_run,
                    log=log,
                )
                per_table[table_name] = rows
                if rows > 0:
                    if not dry_run:
                        log(f"  [完成] {table_name}: {rows} 行")
                    total_rows += rows
                    total_tables += 1
            except Exception as exc:
                log(f"  [错误] {table_name}: {exc}")
                errors += 1
                per_table[table_name] = -1
    finally:
        if not dry_run:
            _enable_fk_checks(target_engine)

    return {
        "tables": total_tables,
        "rows": total_rows,
        "errors": errors,
        "per_table": per_table,
    }


def verify_row_counts(
    source_engine: Engine,
    target_engine: Engine,
    *,
    log: Callable[[str], None] = print,
) -> dict:
    """逐表对比 COUNT(*)，返回差异列表。"""
    source_tables = set(_table_order(source_engine))
    target_tables = set(_table_order(target_engine))
    common = sorted(source_tables & target_tables)

    mismatches: list[dict[str, Any]] = []
    matched = 0

    for table_name in common:
        src_q = _quote(table_name, _dialect_name(source_engine))
        tgt_q = _quote(table_name, _dialect_name(target_engine))
        with source_engine.connect() as src_conn:
            src_count = src_conn.execute(text(f"SELECT COUNT(*) FROM {src_q}")).scalar() or 0
        with target_engine.connect() as tgt_conn:
            tgt_count = tgt_conn.execute(text(f"SELECT COUNT(*) FROM {tgt_q}")).scalar() or 0

        if int(src_count) != int(tgt_count):
            item = {
                "table": table_name,
                "source_count": int(src_count),
                "target_count": int(tgt_count),
            }
            mismatches.append(item)
            log(f"  [差异] {table_name}: source={src_count} target={tgt_count}")
        else:
            matched += 1

    only_source = sorted(source_tables - target_tables)
    only_target = sorted(target_tables - source_tables)
    for name in only_source:
        log(f"  [仅源] {name}")
    for name in only_target:
        log(f"  [仅目标] {name}")

    ok = not mismatches and not only_source and not only_target
    log(f"校验完成: 一致 {matched} 张表, 差异 {len(mismatches)} 张, "
        f"仅源 {len(only_source)}, 仅目标 {len(only_target)}")

    return {
        "ok": ok,
        "matched": matched,
        "mismatches": mismatches,
        "only_source": only_source,
        "only_target": only_target,
    }
