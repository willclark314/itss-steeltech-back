"""根据联系单看板 Excel，为数据库中已有项目补充缺失的排瓦/排楼板性质。

用法：
    python scripts/supplement_layout_natures.py
"""

from __future__ import annotations

import sqlite3
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCEL_PATH = Path(
    r"C:\Users\willc\Documents\github\itss-steeltech\itss-steeltech-projects\files\联系单看板(4).xlsx"
)
DB_PATH = Path(
    r"C:\Users\willc\Documents\github\itss-steeltech\itss-steeltech-back\db\datas\steeltech.db"
)

LAYOUT_NATURES = ("tile_layout", "floor_deck_layout")
NATURE_CHECK_VALUES = (
    "design",
    "detail",
    "detail_issue",
    "plate_layout",
    "floor_deck_layout",
    "tile_layout",
)


def migrate_floor_deck_constraint(conn: sqlite3.Connection) -> bool:
    ddl = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'project_natures'"
    ).fetchone()
    if not ddl or "floor_deck_layout" in ddl[0]:
        return False

    rows = conn.execute("SELECT project_no, nature, created_at FROM project_natures").fetchall()
    conn.execute("PRAGMA foreign_keys = OFF")
    conn.execute("DROP TABLE IF EXISTS project_natures")
    check_values = ", ".join(f"'{value}'" for value in NATURE_CHECK_VALUES)
    conn.execute(
        f"""
        CREATE TABLE project_natures (
          project_no  TEXT NOT NULL,
          nature      TEXT NOT NULL,
          created_at  TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
          PRIMARY KEY (project_no, nature),
          FOREIGN KEY (project_no) REFERENCES projects (project_no) ON DELETE CASCADE,
          CHECK (nature IN ({check_values}))
        )
        """
    )
    conn.execute(
        "CREATE INDEX IF NOT EXISTS idx_project_natures_project_no ON project_natures (project_no)"
    )
    conn.executemany(
        "INSERT OR IGNORE INTO project_natures (project_no, nature, created_at) VALUES (?, ?, ?)",
        rows,
    )
    conn.execute("PRAGMA foreign_keys = ON")
    return True


def collect_expected_layout_natures(excel_path: Path) -> dict[str, set[str]]:
    sys.path.insert(0, str(ROOT))
    from steeltech_db.import_contact_board import (
        FLOOR_DECK_LAYOUT_CATEGORIES,
        TILE_LAYOUT_CATEGORIES,
        read_contact_board_rows,
        resolve_contact_id,
    )
    from steeltech_db.project_split import resolve_import_project_no

    conn = sqlite3.connect(DB_PATH)
    try:
        board_rows = read_contact_board_rows(excel_path)
        for row in board_rows:
            if not row.received_date:
                row.received_date = datetime.now().strftime("%Y-%m-%d")
            row.contact_id = resolve_contact_id(
                conn,
                row.raw_contact_id,
                row.project_no,
                row.received_date,
            )
    finally:
        conn.close()

    expected: dict[str, set[str]] = defaultdict(set)
    for row in board_rows:
        project_no = resolve_import_project_no(row.project_no, row.contact_id)
        parts = [part.strip() for part in row.category.split(",") if part.strip()]
        for part in parts:
            if part in TILE_LAYOUT_CATEGORIES:
                expected[project_no].add("tile_layout")
            if part in FLOOR_DECK_LAYOUT_CATEGORIES:
                expected[project_no].add("floor_deck_layout")
    return expected


def supplement_layout_natures(excel_path: Path, db_path: Path) -> dict[str, int | list[str]]:
    expected = collect_expected_layout_natures(excel_path)
    now_text = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    conn = sqlite3.connect(db_path)
    try:
        migrated = migrate_floor_deck_constraint(conn)
        existing_projects = {
            row[0]
            for row in conn.execute("SELECT project_no FROM projects").fetchall()
        }
        existing_natures: dict[str, set[str]] = defaultdict(set)
        for project_no, nature in conn.execute(
            "SELECT project_no, nature FROM project_natures"
        ).fetchall():
            existing_natures[project_no].add(nature)

        inserted_tile = 0
        inserted_floor = 0
        skipped_missing_project: list[str] = []

        for project_no, natures in sorted(expected.items()):
            if project_no not in existing_projects:
                skipped_missing_project.append(project_no)
                continue
            for nature in natures:
                if nature in existing_natures[project_no]:
                    continue
                conn.execute(
                    "INSERT OR IGNORE INTO project_natures (project_no, nature, created_at) "
                    "VALUES (?, ?, ?)",
                    (project_no, nature, now_text),
                )
                if nature == "tile_layout":
                    inserted_tile += 1
                elif nature == "floor_deck_layout":
                    inserted_floor += 1

        conn.commit()

        counts = conn.execute(
            "SELECT nature, COUNT(*) FROM project_natures "
            "WHERE nature IN ('tile_layout', 'floor_deck_layout') GROUP BY nature"
        ).fetchall()

        return {
            "migrated_constraint": int(migrated),
            "excel_tile_projects": sum(1 for natures in expected.values() if "tile_layout" in natures),
            "excel_floor_projects": sum(
                1 for natures in expected.values() if "floor_deck_layout" in natures
            ),
            "inserted_tile": inserted_tile,
            "inserted_floor": inserted_floor,
            "skipped_missing_project": skipped_missing_project,
            "db_counts": dict(counts),
        }
    finally:
        conn.close()


def main() -> int:
    excel_path = EXCEL_PATH.expanduser().resolve()
    db_path = DB_PATH.expanduser().resolve()

    if not excel_path.exists():
        print(f"Excel 文件不存在: {excel_path}", file=sys.stderr)
        return 1
    if not db_path.exists():
        print(f"数据库文件不存在: {db_path}", file=sys.stderr)
        return 1

    result = supplement_layout_natures(excel_path, db_path)
    print(f"Excel: {excel_path}")
    print(f"数据库: {db_path}")
    print(f"- 约束迁移: {'是' if result['migrated_constraint'] else '否'}")
    print(f"- 看板含排瓦项目: {result['excel_tile_projects']}")
    print(f"- 看板含排楼板项目: {result['excel_floor_projects']}")
    print(f"- 新增排瓦性质: {result['inserted_tile']}")
    print(f"- 新增排楼板性质: {result['inserted_floor']}")
    print(f"- 数据库排瓦/排楼板计数: {result['db_counts']}")
    skipped = result["skipped_missing_project"]
    if skipped:
        print(f"- Excel 有但数据库无项目: {len(skipped)} 个")
        for project_no in skipped[:10]:
            print(f"  · {project_no}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
