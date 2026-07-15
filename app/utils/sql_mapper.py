"""SQL Mapper — 从 .sql 文件加载命名查询，自动绑定参数。

用法:
    mapper = SQLMapper("project")   # 加载 app/sql/project.sql
    row = mapper.one("get_by_no", project_no="P2026001")
    rows = mapper.all("list_page", year="2026", offset=0, limit=20)
    count = mapper.scalar("count_all", year="2026")
    mapper.execute("delete_by_no", project_no="P2026001")  # db.session.commit()
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from sqlalchemy import text

from steeltech_db.extensions import db


class SQLMapper:
    """加载 .sql 文件中的命名查询块，提供参数自动绑定。"""

    def __init__(self, name: str):
        self._name = name
        self._queries: dict[str, str] = {}
        self._load()

    def _sql_dir(self) -> Path:
        return Path(__file__).resolve().parents[1] / "sql"

    def _load(self) -> None:
        file_path = self._sql_dir() / f"{self._name}.sql"
        if not file_path.exists():
            return

        raw = file_path.read_text(encoding="utf-8")
        # 按 -- name: xxx 分块
        blocks = re.split(r"\n-- name:\s*(\S+)", raw)
        # blocks[0] 是第一个 name 前的内容（文件头注释），跳过
        for i in range(1, len(blocks), 2):
            query_name = blocks[i].strip()
            sql = blocks[i + 1].strip() if i + 1 < len(blocks) else ""
            # 去掉 -- params: 注释行
            sql = re.sub(r"\n-- params:.*", "", sql).strip()
            self._queries[query_name] = sql

    def _get_sql(self, name: str) -> str:
        sql = self._queries.get(name)
        if not sql:
            raise KeyError(f"查询 '{name}' 不存在于 {self._name}.sql")
        return sql

    def one(self, name: str, **params: Any) -> Any | None:
        """返回单行结果，无结果返回 None。"""
        return db.session.execute(text(self._get_sql(name)), params).first()

    def all(self, name: str, **params: Any) -> list[Any]:
        """返回所有行。"""
        return list(db.session.execute(text(self._get_sql(name)), params).all())

    def scalar(self, name: str, **params: Any) -> Any:
        """返回单个标量值。"""
        return db.session.execute(text(self._get_sql(name)), params).scalar()

    def execute(self, name: str, **params: Any) -> None:
        """执行写操作（INSERT/UPDATE/DELETE），自动 commit。"""
        db.session.execute(text(self._get_sql(name)), params)
        db.session.commit()


# 预加载常用 mapper（懒加载，首次访问时读文件）
_mapper_cache: dict[str, SQLMapper] = {}


def mapper(name: str) -> SQLMapper:
    """获取指定名称的 SQLMapper 单例。"""
    if name not in _mapper_cache:
        _mapper_cache[name] = SQLMapper(name)
    return _mapper_cache[name]
