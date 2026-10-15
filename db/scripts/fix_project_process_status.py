"""按单主任务流程完成规则修正项目 status / actual_end_date。"""

from __future__ import annotations

import argparse
import sqlite3
from datetime import datetime
from pathlib import Path


def get_natures(cur: sqlite3.Cursor, project_no: str) -> list[str]:
    return [row[0] for row in cur.execute(
        "SELECT nature FROM project_natures WHERE project_no = ?",
        (project_no,),
    ).fetchall()]


def has_dual_nature_tasks(natures: list[str]) -> bool:
    return "design" in natures and "detail" in natures


def completion_sync_kind(natures: list[str]) -> str | None:
    if has_dual_nature_tasks(natures):
        return None
    if "design" in natures:
        return "design"
    if "detail" in natures:
        return "detail"
    return None


def is_detail_process_completed(
    cur: sqlite3.Cursor,
    project_no: str,
    natures: list[str],
    *,
    manual_detail_completed: bool,
) -> bool:
    if "detail" not in natures:
        return manual_detail_completed
    workflow = cur.execute(
        """
        SELECT drawing_status, plate_layout_enabled, plate_layout_status
        FROM project_detail_workflows
        WHERE project_no = ?
        """,
        (project_no,),
    ).fetchone()
    if workflow is None:
        return False
    if workflow["drawing_status"] != "completed":
        return False
    if workflow["plate_layout_enabled"] and workflow["plate_layout_status"] != "completed":
        return False
    return True


def should_process_be_done(
    cur: sqlite3.Cursor,
    project_no: str,
    natures: list[str],
    sync_kind: str,
    *,
    design_completed: bool,
    detail_completed: bool,
) -> bool:
    if sync_kind == "design":
        return bool(design_completed)
    return is_detail_process_completed(
        cur,
        project_no,
        natures,
        manual_detail_completed=bool(detail_completed),
    )


def analyze(conn: sqlite3.Connection) -> tuple[list[dict], list[dict]]:
    cur = conn.cursor()
    to_done: list[dict] = []
    to_active: list[dict] = []

    rows = cur.execute(
        """
        SELECT project_no, name, status, design_completed, detail_completed, actual_end_date
        FROM projects
        """
    ).fetchall()

    for row in rows:
        natures = get_natures(cur, row["project_no"])
        sync_kind = completion_sync_kind(natures)
        if sync_kind is None:
            continue

        expected_done = should_process_be_done(
            cur,
            row["project_no"],
            natures,
            sync_kind,
            design_completed=bool(row["design_completed"]),
            detail_completed=bool(row["detail_completed"]),
        )
        item = {
            "project_no": row["project_no"],
            "name": row["name"],
            "sync_kind": sync_kind,
            "status": row["status"],
            "design_completed": bool(row["design_completed"]),
            "detail_completed": bool(row["detail_completed"]),
        }

        if expected_done and row["status"] == "active":
            to_done.append(item)
        elif not expected_done and row["status"] == "done":
            to_active.append(item)

    return to_done, to_active


def apply_fixes(conn: sqlite3.Connection, to_done: list[dict], to_active: list[dict]) -> None:
    cur = conn.cursor()
    now = datetime.now().strftime("%Y-%m-%d")
    now_ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    for item in to_done:
        cur.execute(
            """
            UPDATE projects
            SET status = 'done',
                actual_end_date = CASE
                  WHEN TRIM(IFNULL(actual_end_date, '')) = '' THEN ?
                  ELSE actual_end_date
                END,
                updated_at = ?
            WHERE project_no = ?
            """,
            (now, now_ts, item["project_no"]),
        )

    for item in to_active:
        cur.execute(
            """
            UPDATE projects
            SET status = 'active',
                actual_end_date = '',
                updated_at = ?
            WHERE project_no = ?
            """,
            (now_ts, item["project_no"]),
        )

    conn.commit()


def main() -> None:
    parser = argparse.ArgumentParser(description="修正单主任务项目的流程状态")
    parser.add_argument(
        "--db",
        type=Path,
        default=Path(__file__).resolve().parent.parent / "datas" / "steeltech.db",
        help="SQLite 数据库路径",
    )
    parser.add_argument("--apply", action="store_true", help="执行修正（默认仅预览）")
    args = parser.parse_args()

    if not args.db.exists():
        raise SystemExit(f"数据库不存在: {args.db}")

    conn = sqlite3.connect(args.db)
    conn.row_factory = sqlite3.Row

    to_done, to_active = analyze(conn)

    print(f"数据库: {args.db}")
    print(f"应改为已完成 (active -> done): {len(to_done)}")
    for item in to_done:
        print(f"  [{item['sync_kind']}] {item['project_no']} {item['name']}")

    print(f"应改回进行中 (done -> active): {len(to_active)}")
    for item in to_active:
        print(
            f"  [{item['sync_kind']}] {item['project_no']} {item['name']} "
            f"(design={int(item['design_completed'])}, detail={int(item['detail_completed'])})"
        )

    if args.apply:
        apply_fixes(conn, to_done, to_active)
        print("已应用修正。")
    else:
        print("预览模式，未写入。使用 --apply 执行修正。")

    conn.close()


if __name__ == "__main__":
    main()
