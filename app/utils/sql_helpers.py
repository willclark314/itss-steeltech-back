"""跨数据库 SQL 辅助函数。"""

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import text

from steeltech_db.extensions import db


def insert_ignore(table: str, columns: str) -> str:
    """生成跨数据库的 INSERT IGNORE 语句前缀。

    SQLite: INSERT OR IGNORE INTO <table> (<columns>)
    MySQL:  INSERT IGNORE INTO <table> (<columns>)
    """
    bind = db.session.get_bind()
    if bind.dialect.name == "mysql":
        return f"INSERT IGNORE INTO {table} ({columns})"
    return f"INSERT OR IGNORE INTO {table} ({columns})"


def insert_replace(table: str, columns: str) -> str:
    """生成跨数据库的 INSERT OR REPLACE / REPLACE INTO 语句前缀。

    SQLite: INSERT OR REPLACE INTO <table> (<columns>)
    MySQL:  REPLACE INTO <table> (<columns>)
    """
    bind = db.session.get_bind()
    if bind.dialect.name == "mysql":
        return f"REPLACE INTO {table} ({columns})"
    return f"INSERT OR REPLACE INTO {table} ({columns})"


def now_expr() -> str:
    """生成跨数据库的当前时间表达式。

    SQLite: datetime('now', 'localtime')
    MySQL:  NOW()
    """
    bind = db.session.get_bind()
    if bind.dialect.name == "mysql":
        return "NOW()"
    return "datetime('now', 'localtime')"


def is_mysql() -> bool:
    """当前数据库后端是否为 MySQL。"""
    bind = db.session.get_bind()
    return bind.dialect.name == "mysql"


def is_sqlite() -> bool:
    """当前数据库后端是否为 SQLite。"""
    bind = db.session.get_bind()
    return bind.dialect.name == "sqlite"


@contextmanager
def disable_foreign_keys() -> Iterator[None]:
    """跨数据库禁用/恢复外键约束的上下文管理器。

    SQLite: PRAGMA foreign_keys = OFF / ON
    MySQL:  SET FOREIGN_KEY_CHECKS = 0 / 1

    用法:
        with disable_foreign_keys():
            db.session.execute(text("UPDATE ..."))
    """
    bind = db.session.get_bind()
    if bind.dialect.name == "mysql":
        db.session.execute(text("SET FOREIGN_KEY_CHECKS = 0"))
        try:
            yield
        finally:
            db.session.execute(text("SET FOREIGN_KEY_CHECKS = 1"))
    else:
        db.session.execute(text("PRAGMA foreign_keys = OFF"))
        try:
            yield
        finally:
            db.session.execute(text("PRAGMA foreign_keys = ON"))
