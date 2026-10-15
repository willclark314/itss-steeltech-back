"""SQLite ↔ MySQL 双向迁移 CLI。

用法:
    # 预览（不写入）
    python scripts/migrate_db.py --source sqlite:///path/to/steeltech.db \\
        --target mysql+pymysql://user:pass@127.0.0.1:3306/itss_steeltech --dry-run

    # 执行迁移（upsert）
    python scripts/migrate_db.py --source sqlite:///... --target mysql+pymysql://...

    # 干净覆盖（先清空目标业务表再插入）
    python scripts/migrate_db.py --source mysql+pymysql://... --target sqlite:///... --mode replace

    # 仅行数校验
    python scripts/migrate_db.py --verify-only --source ... --target ...

也可省略 --source：默认使用当前环境 DATABASE_URL / 默认 SQLite 路径。
省略 --target 时必须显式传入。
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# 保证可从仓库根或 scripts 目录运行
_DB_ROOT = Path(__file__).resolve().parents[1]
if str(_DB_ROOT) not in sys.path:
    sys.path.insert(0, str(_DB_ROOT))

load_dotenv()
load_dotenv(_DB_ROOT.parent / ".env")


def _default_source_url() -> str:
    url = os.getenv("DATABASE_URL") or os.getenv("SQLALCHEMY_DATABASE_URI") or ""
    if url:
        return url
    from steeltech_db.config import BaseConfig

    return f"sqlite:///{BaseConfig.SQLITE_DATABASE_PATH.as_posix()}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SQLite <-> MySQL bidirectional database migration")
    parser.add_argument("--source", default="", help="源库 SQLAlchemy URI")
    parser.add_argument("--target", default="", help="目标库 SQLAlchemy URI")
    parser.add_argument(
        "--mode",
        choices=("upsert", "replace"),
        default="upsert",
        help="upsert=按主键合并；replace=先清空目标表再插入",
    )
    parser.add_argument("--dry-run", action="store_true", help="仅预览，不写入")
    parser.add_argument("--verify-only", action="store_true", help="仅做行数校验")
    parser.add_argument(
        "--no-ensure-schema",
        action="store_true",
        help="跳过目标库建表/补丁（假定目标已就绪）",
    )
    parser.add_argument(
        "--no-verify",
        action="store_true",
        help="迁移后不做行数校验",
    )
    args = parser.parse_args(argv)

    source_url = (args.source or "").strip() or _default_source_url()
    target_url = (args.target or "").strip()
    if not target_url:
        print("错误: 必须提供 --target 目标库 URI")
        print("示例: --target mysql+pymysql://root:pass@127.0.0.1:3306/itss_steeltech")
        return 1

    from steeltech_db.db_migrate import migrate_database, verify_databases

    if args.verify_only:
        result = verify_databases(source_url, target_url)
        return 0 if result.get("ok") else 1

    result = migrate_database(
        source_url,
        target_url,
        dry_run=args.dry_run,
        mode=args.mode,
        ensure_schema=not args.no_ensure_schema,
        verify=not args.no_verify,
    )

    sync = result.get("sync") or {}
    print()
    print(
        f"同步{'预览' if args.dry_run else ''}完成: "
        f"{sync.get('tables', 0)} 张表, {sync.get('rows', 0)} 行, "
        f"{sync.get('errors', 0)} 错误"
    )
    verify = result.get("verify")
    if verify is not None:
        print(f"校验: {'通过' if verify.get('ok') else '未通过'}")

    return 0 if result.get("ok") else 1


if __name__ == "__main__":
    sys.exit(main())
