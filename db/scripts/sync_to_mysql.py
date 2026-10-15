"""SQLite → MySQL 数据同步 CLI（兼容入口，转发至 migrate_database）。

用法:
    python scripts/sync_to_mysql.py --dry-run
    python scripts/sync_to_mysql.py

环境变量:
    DATABASE_URL: 目标 MySQL 连接字符串
    源库默认使用包内 datas/steeltech.db（或配置中的默认 SQLite 路径）
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

_DB_ROOT = Path(__file__).resolve().parents[1]
if str(_DB_ROOT) not in sys.path:
    sys.path.insert(0, str(_DB_ROOT))

load_dotenv()
load_dotenv(_DB_ROOT.parent / ".env")


def main() -> None:
    dry_run = "--dry-run" in sys.argv

    database_url = os.getenv("DATABASE_URL") or os.getenv("SQLALCHEMY_DATABASE_URI") or ""
    if not database_url:
        print("错误: 未设置 DATABASE_URL 环境变量")
        print("示例: DATABASE_URL=mysql+pymysql://root:password@127.0.0.1:3306/itss_steeltech")
        sys.exit(1)

    if not (database_url.startswith("mysql:") or database_url.startswith("mysql+")):
        print(f"错误: DATABASE_URL 不是 MySQL 连接串: {database_url[:40]}...")
        sys.exit(1)

    default_sqlite = (_DB_ROOT / "datas" / "steeltech.db").resolve()
    sqlite_path = default_sqlite
    if not sqlite_path.exists():
        print(f"错误: SQLite 数据库文件不存在: {sqlite_path}")
        sys.exit(1)

    source_url = f"sqlite:///{sqlite_path.as_posix()}"

    from steeltech_db.db_migrate import migrate_database

    result = migrate_database(
        source_url,
        database_url,
        dry_run=dry_run,
        mode="upsert",
        ensure_schema=True,
        verify=not dry_run,
    )
    sync = result.get("sync") or {}
    print()
    print(
        f"同步{'预览' if dry_run else ''}完成: "
        f"{sync.get('tables', 0)} 张表, {sync.get('rows', 0)} 行, "
        f"{sync.get('errors', 0)} 错误"
    )
    sys.exit(0 if result.get("ok") else 1)


if __name__ == "__main__":
    main()
