"""终端输出格式化工具。"""

from __future__ import annotations


def print_section(title: str) -> None:
    print()
    print(f"=== {title} ===")


def print_kv_rows(rows: list[tuple[str, str | int]], *, key_width: int = 28) -> None:
    if not rows:
        print("  (无数据)")
        return
    width = max(key_width, max(len(str(key)) for key, _ in rows))
    for key, value in rows:
        print(f"  {str(key):<{width}}  {value}")


def print_table(headers: list[str], rows: list[list[str | int]], *, max_rows: int | None = None) -> None:
    if not rows:
        print("  (无数据)")
        return

    display_rows = rows[:max_rows] if max_rows is not None else rows
    str_rows = [[str(cell) for cell in row] for row in display_rows]
    widths = [
        max(len(headers[i]), *(len(row[i]) for row in str_rows))
        for i in range(len(headers))
    ]

    header_line = "  ".join(header.ljust(widths[i]) for i, header in enumerate(headers))
    print(f"  {header_line}")
    print(f"  {'  '.join('-' * width for width in widths)}")
    for row in str_rows:
        print(f"  {'  '.join(cell.ljust(widths[i]) for i, cell in enumerate(row))}")

    omitted = len(rows) - len(display_rows)
    if omitted > 0:
        print(f"  ... 另有 {omitted} 行未显示")
