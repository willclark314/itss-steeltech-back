"""后端本地附件存储目录统计（datas/files）。

用法（在后端根目录）：
  python scripts/storage_stats.py
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from _bootstrap import app_context
from _format import print_kv_rows, print_section, print_table


@dataclass
class DirStats:
    label: str
    root: Path
    file_count: int
    total_bytes: int


def _human_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            if unit == "B":
                return f"{int(size)} {unit}"
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def _scan_dir(label: str, root: Path) -> DirStats:
    file_count = 0
    total_bytes = 0
    if root.is_dir():
        for dirpath, _, filenames in os.walk(root):
            for filename in filenames:
                file_path = Path(dirpath) / filename
                try:
                    total_bytes += file_path.stat().st_size
                except OSError:
                    continue
                file_count += 1
    return DirStats(label=label, root=root, file_count=file_count, total_bytes=total_bytes)


def main() -> int:
    with app_context() as app:
        from app.config import Config

        roots = [
            ("联系单 PDF", Config.CONTACT_PDF_STORAGE_ROOT),
            ("联系单附件", Config.CONTACT_ATTACHMENT_STORAGE_ROOT),
            ("周会图片", Config.WEEKLY_MEETING_IMAGE_ROOT),
            ("周会扫描件", Config.WEEKLY_MEETING_SCAN_ROOT),
            ("所长访谈图片", Config.DIRECTOR_INTERVIEW_IMAGE_ROOT),
            ("变更单 PDF", Config.CHANGE_ORDER_PDF_STORAGE_ROOT),
            ("月度培训文件", Config.MONTHLY_TRAINING_FILE_ROOT),
        ]

        print_section("存储根目录")
        print_kv_rows([("后端根目录", Config.BASE_DIR)])

        stats = [_scan_dir(label, Path(path)) for label, path in roots]

        print_section("各目录文件统计")
        print_table(
            ["目录", "文件数", "体积", "路径"],
            [
                [
                    item.label,
                    item.file_count,
                    _human_size(item.total_bytes),
                    str(item.root),
                ]
                for item in stats
            ],
        )

        total_files = sum(item.file_count for item in stats)
        total_bytes = sum(item.total_bytes for item in stats)
        print_section("合计")
        print_kv_rows(
            [
                ("目录数", len(stats)),
                ("文件总数", total_files),
                ("总体积", _human_size(total_bytes)),
            ]
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
