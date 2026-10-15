"""项目工作路径与文件夹可达性统计。

用法（在后端根目录）：
  python scripts/project_folder_stats.py
  python scripts/project_folder_stats.py --check-exists
  python scripts/project_folder_stats.py --missing-only
"""

from __future__ import annotations

import argparse
import os
from dataclasses import dataclass

from sqlalchemy import func

from _bootstrap import app_context
from _format import print_kv_rows, print_section, print_table


@dataclass
class PathCheck:
    project_no: str
    name: str
    path_type: str
    relative_path: str
    full_path: str
    exists: bool | None


def _path_exists(full_path: str) -> bool | None:
    if not full_path:
        return None
    try:
        return os.path.isdir(normalize_access_path(full_path))
    except OSError:
        return False


def _collect_checks(projects, *, check_exists: bool) -> list[PathCheck]:
    from app.utils.paths import build_full_path, normalize_access_path, normalize_relative_path

    checks: list[PathCheck] = []
    for project in projects:
        candidates = [
            ("design", project.design_work_path),
            ("detail", project.detail_work_path),
            ("local", project.local_work_path),
        ]
        for path_type, raw_path in candidates:
            relative = normalize_relative_path(raw_path or "")
            if not relative:
                continue
            full_path = build_full_path(relative)
            exists = _path_exists(full_path) if check_exists else None
            checks.append(
                PathCheck(
                    project_no=project.project_no,
                    name=project.name,
                    path_type=path_type,
                    relative_path=relative,
                    full_path=full_path,
                    exists=exists,
                )
            )
    return checks


def main() -> int:
    parser = argparse.ArgumentParser(description="统计项目工作路径与文件夹状态")
    parser.add_argument(
        "--check-exists",
        action="store_true",
        help="尝试访问 UNC 路径并检查文件夹是否存在（需本机可访问文件服务器）",
    )
    parser.add_argument(
        "--missing-only",
        action="store_true",
        help="仅列出未填写任何工作路径的项目",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=30,
        help="明细表最多显示行数（默认 30）",
    )
    args = parser.parse_args()

    with app_context():
        from app.services.system_config_service import get_local_work_path_config
        from app.utils.paths import normalize_relative_path
        from steeltech_db.extensions import db
        from steeltech_db.models import Project

        config = get_local_work_path_config()
        print_section("本地工作路径配置")
        print_kv_rows(
            [
                ("默认 IP", config.get("ip", "")),
                ("备用 IP 数", len(config.get("ips") or [])),
            ]
        )

        projects = Project.query.order_by(Project.project_no).all()
        total = len(projects)

        with_any = Project.query.filter(
            db.or_(
                func.length(func.trim(Project.design_work_path)) > 0,
                func.length(func.trim(Project.detail_work_path)) > 0,
                func.length(func.trim(Project.local_work_path)) > 0,
            )
        ).count()

        print_section("路径填写概览")
        print_kv_rows(
            [
                ("项目总数", total),
                ("至少有一条路径", with_any),
                ("三条路径均未填", total - with_any),
            ]
        )

        if args.missing_only:
            missing_projects = [
                project
                for project in projects
                if not any(
                    normalize_relative_path(path or "")
                    for path in (
                        project.design_work_path,
                        project.detail_work_path,
                        project.local_work_path,
                    )
                )
            ]
            print_section("未填写工作路径的项目")
            print_table(
                ["项目号", "名称", "状态"],
                [[p.project_no, p.name, p.status] for p in missing_projects],
                max_rows=args.limit,
            )
            return 0

        checks = _collect_checks(projects, check_exists=args.check_exists)

        print_section("已登记路径条数（按类型）")
        by_type: dict[str, int] = {}
        for item in checks:
            by_type[item.path_type] = by_type.get(item.path_type, 0) + 1
        print_kv_rows(sorted(by_type.items()))

        if args.check_exists:
            existing = sum(1 for item in checks if item.exists is True)
            missing = sum(1 for item in checks if item.exists is False)
            print_section("文件夹可达性（已登记路径）")
            print_kv_rows(
                [
                    ("可访问", existing),
                    ("不可访问或不存在", missing),
                    ("检查总数", len(checks)),
                ]
            )

            bad_rows = [
                [item.project_no, item.path_type, item.relative_path]
                for item in checks
                if item.exists is False
            ]
            if bad_rows:
                print_section("不可访问的路径（节选）")
                print_table(["项目号", "类型", "相对路径"], bad_rows, max_rows=args.limit)
        else:
            print_section("已登记路径样例")
            sample_rows = [
                [item.project_no, item.path_type, item.relative_path]
                for item in checks[: args.limit]
            ]
            print_table(["项目号", "类型", "相对路径"], sample_rows)
            print()
            print("  提示：加 --check-exists 可检测 UNC 路径是否在本机可访问。")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
