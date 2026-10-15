"""从联系单看板 Excel 更新数据库（支持 SQLite / MySQL）。

通过 DATABASE_URL 环境变量自动选择数据库后端。
默认 SQLite: sqlite:///<backend>/db/datas/steeltech.db

使用方式：
    python scripts/import_contact_board.py
    # 或指定 Excel 路径：
    python scripts/import_contact_board.py /path/to/file.xlsx
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DB_DIR = ROOT / "datas"

# ===== Excel 文件路径（可命令行覆盖）=====
EXCEL_PATH = Path(
    r"C:\Users\willc\Documents\github\itss-steeltech\itss-steeltech-projects\files\联系单看板(3).xlsx"
)


def _get_database_url() -> str:
    """从环境变量或默认路径获取数据库连接。"""
    url = os.getenv("DATABASE_URL") or os.getenv("SQLALCHEMY_DATABASE_URI") or ""
    if url.strip():
        return url.strip()
    db_path = DB_DIR / "steeltech.db"
    return f"sqlite:///{db_path.as_posix()}"


def main() -> int:
    from sqlalchemy import create_engine

    excel_path = EXCEL_PATH.expanduser().resolve()
    if len(sys.argv) > 1:
        excel_path = Path(sys.argv[1]).expanduser().resolve()

    if not excel_path.exists():
        print(f"Excel 文件不存在: {excel_path}", file=sys.stderr)
        return 1

    database_url = _get_database_url()
    sys.path.insert(0, str(ROOT))
    from steeltech_db.import_contact_board import import_contact_board_to_engine

    engine = create_engine(database_url)
    try:
        stats = import_contact_board_to_engine(excel_path, engine)
    finally:
        engine.dispose()

    print(f"Excel: {excel_path}")
    print(f"数据库: {database_url.split('@')[-1] if '@' in database_url else database_url}")
    print(f"- 读取行数: {stats.rows_read}")
    print(f"- 跳过行数: {stats.rows_skipped}")
    print(f"- 项目更新: {stats.projects_upserted}")
    print(f"- 联系单更新: {stats.contacts_upserted}")
    print(f"- 关联写入: {stats.links_synced}")
    print(f"- 性质关联: {stats.nature_links}")
    print(f"- 人员关联: {stats.personnel_links}")
    if stats.warnings:
        print(f"- 警告 {len(stats.warnings)} 条（仅显示前 10 条）:")
        for warning in stats.warnings[:10]:
            print(f"  · {warning}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
