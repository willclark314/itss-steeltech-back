"""数据库概览统计。

用法（在后端根目录）：
  python scripts/db_stats.py
  python scripts/db_stats.py --tables
"""

from __future__ import annotations

import argparse
from collections import Counter

from sqlalchemy import func, inspect

from _bootstrap import app_context
from _format import print_kv_rows, print_section, print_table


def _count_by(model, column):
    from steeltech_db.extensions import db

    rows = (
        db.session.query(getattr(model, column), func.count())
        .group_by(getattr(model, column))
        .order_by(func.count().desc())
        .all()
    )
    return [(value or "(空)", count) for value, count in rows]


def _table_row_counts() -> list[tuple[str, int]]:
    from steeltech_db.extensions import db

    inspector = inspect(db.engine)
    skip = {"alembic_version", "backup_records"}
    counts: list[tuple[str, int]] = []
    for table in sorted(inspector.get_table_names()):
        if table in skip:
            continue
        row = db.session.execute(db.text(f"SELECT COUNT(*) FROM `{table}`")).scalar()
        counts.append((table, int(row or 0)))
    return counts


def main() -> int:
    parser = argparse.ArgumentParser(description="输出数据库概览统计")
    parser.add_argument(
        "--tables",
        action="store_true",
        help="列出各业务表行数（默认仅显示核心摘要）",
    )
    args = parser.parse_args()

    with app_context() as app:
        from app.config import Config
        from steeltech_db.extensions import db
        from steeltech_db.models import (
            ContactForm,
            ContactFormPdf,
            Personnel,
            Project,
            Role,
        )

        print_section("连接信息")
        print_kv_rows(
            [
                ("DATABASE_BACKEND", app.config.get("DATABASE_BACKEND", "sqlite")),
                ("SQLALCHEMY_DATABASE_URI", app.config.get("SQLALCHEMY_DATABASE_URI", "")),
                ("SQLite 路径", Config.SQLITE_DATABASE_PATH),
            ]
        )

        print_section("核心表行数")
        print_kv_rows(
            [
                ("人员 personnel", Personnel.query.count()),
                ("角色 roles", Role.query.count()),
                ("项目 projects", Project.query.count()),
                ("联系单 contact_forms", ContactForm.query.count()),
                ("联系单 PDF contact_form_pdfs", ContactFormPdf.query.count()),
            ]
        )

        print_section("项目按状态")
        print_kv_rows(_count_by(Project, "status"))

        print_section("人员按状态")
        print_kv_rows(_count_by(Personnel, "status"))

        print_section("人员按班组")
        print_kv_rows(_count_by(Personnel, "team"))

        print_section("联系单（未软删）按状态")
        active_contacts = ContactForm.query.filter(ContactForm.deleted_at.is_(None))
        status_counter = Counter(row.status for row in active_contacts.with_entities(ContactForm.status))
        print_kv_rows(sorted(status_counter.items(), key=lambda item: (-item[1], item[0])))

        print_section("项目路径填写情况")
        total = Project.query.count()
        with_design = Project.query.filter(
            func.length(func.trim(Project.design_work_path)) > 0
        ).count()
        with_detail = Project.query.filter(
            func.length(func.trim(Project.detail_work_path)) > 0
        ).count()
        with_local = Project.query.filter(
            func.length(func.trim(Project.local_work_path)) > 0
        ).count()
        with_any = Project.query.filter(
            db.or_(
                func.length(func.trim(Project.design_work_path)) > 0,
                func.length(func.trim(Project.detail_work_path)) > 0,
                func.length(func.trim(Project.local_work_path)) > 0,
            )
        ).count()
        print_kv_rows(
            [
                ("项目总数", total),
                ("已填设计路径", with_design),
                ("已填细化路径", with_detail),
                ("已填本地路径", with_local),
                ("至少有一条路径", with_any),
                ("三条路径均未填", total - with_any),
            ]
        )

        if args.tables:
            print_section("全部业务表行数")
            print_table(["表名", "行数"], [[name, count] for name, count in _table_row_counts()])

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
