"""数据库连接配置解析 —— 支持 DATABASE_URL 与 legacy 分散变量。"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping
from urllib.parse import unquote

from sqlalchemy.engine.url import make_url


def detect_backend(database_uri: str) -> str:
    """从 SQLAlchemy URI 推断后端类型（sqlite / mysql）。"""
    driver = make_url(database_uri).drivername
    if driver.startswith("mysql"):
        return "mysql"
    if driver.startswith("sqlite"):
        return "sqlite"
    raise ValueError(f"Unsupported database URL driver: {driver}")


def sqlite_path_from_uri(database_uri: str) -> Path | None:
    """从 SQLite URI 解析数据库文件路径；内存库返回 None。"""
    url = make_url(database_uri)
    if not url.drivername.startswith("sqlite"):
        return None

    database = url.database
    if not database or database == ":memory:":
        return None

    path = Path(unquote(database))
    if not path.is_absolute():
        path = Path.cwd() / path
    return path.resolve()


def mysql_params_from_uri(database_uri: str) -> dict[str, str | int]:
    """从 MySQL URI 解析连接参数。"""
    url = make_url(database_uri)
    if not url.drivername.startswith("mysql"):
        raise ValueError(f"Not a MySQL URL: {database_uri}")

    return {
        "MYSQL_HOST": url.host or "127.0.0.1",
        "MYSQL_PORT": url.port or 3306,
        "MYSQL_USER": unquote(url.username or "root"),
        "MYSQL_PASSWORD": unquote(url.password or ""),
        "MYSQL_DATABASE": unquote((url.database or "itss_steeltech")),
    }


def build_mysql_uri(
    *,
    host: str,
    port: int,
    user: str,
    password: str,
    database: str,
) -> str:
    return (
        f"mysql+pymysql://{user}:{password}"
        f"@{host}:{port}/{database}?charset=utf8mb4"
    )


def build_sqlite_uri(path: Path) -> str:
    return "sqlite:///" + path.as_posix()


def resolve_database_settings(
    env: Mapping[str, str] | None = None,
    *,
    default_sqlite_path: Path,
) -> dict[str, object]:
    """解析数据库配置，仅支持 DATABASE_URL（或 SQLALCHEMY_DATABASE_URI）字符串模式。

    未设置时默认使用 SQLite，数据库文件位于 default_sqlite_path。
    """
    source = env if env is not None else os.environ

    database_url = (
        source.get("DATABASE_URL") or source.get("SQLALCHEMY_DATABASE_URI") or ""
    ).strip()

    if not database_url:
        database_url = build_sqlite_uri(default_sqlite_path)

    backend = detect_backend(database_url)
    settings: dict[str, object] = {
        "DATABASE_BACKEND": backend,
        "SQLALCHEMY_DATABASE_URI": database_url,
    }

    if backend == "sqlite":
        sqlite_path = sqlite_path_from_uri(database_url) or default_sqlite_path
        sqlite_path.parent.mkdir(parents=True, exist_ok=True)
        settings["SQLITE_DATABASE_PATH"] = sqlite_path
    else:
        settings.update(mysql_params_from_uri(database_url))
        settings["SQLITE_DATABASE_PATH"] = default_sqlite_path

    return settings
