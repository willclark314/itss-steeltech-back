"""将当前数据库全表导出为 Excel（每表一个 Sheet），便于发给同事清理数据。

用法：
  python scripts/export_to_excel.py
  python scripts/export_to_excel.py --out D:/share/steeltech.xlsx

连接串优先读环境变量 DATABASE_URL；未设置时读后端 .env，再回退本地 MySQL。
"""

from __future__ import annotations

import argparse
import os
import re
from datetime import datetime
from pathlib import Path
from urllib.parse import unquote, urlparse

import pandas as pd
from sqlalchemy import create_engine, inspect, text

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_URL = "mysql+pymysql://root:123456@127.0.0.1:3306/itss_steeltech?charset=utf8mb4"
DEFAULT_OUT_DIR = ROOT / "datas" / "exports"

SKIP_TABLES = {
    "backup_records",
    "alembic_version",
}

MASK_COLUMNS: dict[str, set[str]] = {
    "account_passwords": {"password"},
}


def resolve_database_url() -> str:
    url = (os.environ.get("DATABASE_URL") or os.environ.get("SQLALCHEMY_DATABASE_URI") or "").strip()
    if url:
        return url
    env_path = ROOT.parent / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            if key.strip() == "DATABASE_URL":
                value = value.strip().strip('"').strip("'")
                if value and not value.startswith("#"):
                    return value
    return DEFAULT_URL


def sheet_name(table: str) -> str:
    name = re.sub(r"[\\/?*\[\]]", "_", table)
    return name[:31]


def main() -> int:
    parser = argparse.ArgumentParser(description="导出数据库为 Excel")
    parser.add_argument("--out", type=Path, default=None, help="输出 xlsx 路径")
    parser.add_argument("--url", default=None, help="数据库连接串")
    args = parser.parse_args()

    url = args.url or resolve_database_url()
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = (args.out or (DEFAULT_OUT_DIR / f"itss_steeltech_export_{stamp}.xlsx")).expanduser().resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(url)
    tables = sorted(t for t in inspect(engine).get_table_names() if t not in SKIP_TABLES)

    frames: dict[str, pd.DataFrame] = {}
    summary_rows: list[dict] = []

    with engine.connect() as conn:
        for table in tables:
            df = pd.read_sql(text(f"SELECT * FROM `{table}`"), conn)
            for col in MASK_COLUMNS.get(table, set()):
                if col in df.columns:
                    df[col] = "***"
            name = sheet_name(table)
            frames[name] = df
            summary_rows.append(
                {"table": table, "rows": len(df), "columns": len(df.columns), "sheet": name}
            )
            print(f"exported {table}: {len(df)} rows, {len(df.columns)} cols")

    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        pd.DataFrame(summary_rows).to_excel(writer, sheet_name="_目录", index=False)
        for name, df in frames.items():
            df.to_excel(writer, sheet_name=name, index=False)

    parsed = urlparse(url.replace("mysql+pymysql://", "mysql://", 1))
    host = parsed.hostname or "?"
    db_name = (parsed.path or "/").lstrip("/") or "?"
    print(f"source: {host}/{unquote(db_name)}")
    print(f"output: {out_path}")
    print(f"size_mb: {round(out_path.stat().st_size / 1024 / 1024, 2)}")
    print(f"tables: {len(tables)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
