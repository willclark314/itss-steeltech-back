"""数据库迁移编排：建表 → 同步 → 校验 → 切换指引。

流程固定为：迁数据到目标库后，由运维修改 DATABASE_URL 并重启应用。
不支持运行时热切换连接。
"""

from __future__ import annotations

from typing import Callable
from urllib.parse import urlsplit, urlunsplit

from sqlalchemy import create_engine, text
from sqlalchemy.engine import Engine

from steeltech_db.database_url import detect_backend, sqlite_path_from_uri
from steeltech_db.db_sync import SyncMode, sync_databases, verify_row_counts


def mask_database_url(url: str) -> str:
    """脱敏连接串中的密码。"""
    if not url:
        return ""
    try:
        parts = urlsplit(url)
        if not parts.scheme:
            return url
        # netloc may be user:pass@host:port
        netloc = parts.netloc
        if "@" in netloc and ":" in netloc.split("@", 1)[0]:
            userinfo, hostinfo = netloc.rsplit("@", 1)
            user = userinfo.split(":", 1)[0]
            netloc = f"{user}:****@{hostinfo}"
        return urlunsplit((parts.scheme, netloc, parts.path, parts.query, parts.fragment))
    except Exception:
        return url


def probe_engine(engine: Engine) -> None:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))


def create_engine_from_url(database_url: str) -> Engine:
    return create_engine(database_url, pool_pre_ping=True)


def ensure_target_schema(
    target_url: str,
    *,
    log: Callable[[str], None] = print,
) -> None:
    """在目标库上建表并跑 ensure_schema 补丁。

    使用临时 Flask app + 已注册的全局 db 扩展；在目标 app_context 内执行，
    不改写调用方当前进程的 DATABASE_URL。
    """
    from flask import Flask

    import steeltech_db.models  # noqa: F401 — 注册 ORM 元数据
    from steeltech_db.extensions import db
    from steeltech_db.seed import bootstrap_sqlite_file, ensure_schema

    backend = detect_backend(target_url)
    if backend == "sqlite":
        path = sqlite_path_from_uri(target_url)
        if path is not None:
            log(f"准备 SQLite 目标文件: {path}")
            bootstrap_sqlite_file(path)

    app = Flask("steeltech_db_migrate")
    app.config["SQLALCHEMY_DATABASE_URI"] = target_url
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["DEFAULT_LOGIN_PASSWORD"] = "migrate-placeholder"
    app.config["DATABASE_BACKEND"] = backend

    db.init_app(app)
    with app.app_context():
        log(f"目标库建表 / schema 补丁 ({backend}) ...")
        ensure_schema(app)
    log("目标库 schema 就绪")


def switch_instructions(target_url: str) -> dict:
    """生成切换指引（不执行热切换）。"""
    backend = detect_backend(target_url)
    masked = mask_database_url(target_url)
    steps = [
        f"将环境变量 DATABASE_URL 改为目标库（当前后端将变为 {backend}）",
        f"示例: DATABASE_URL={masked}",
        "若使用 Docker Compose，同步修改 docker-compose.yml / .env 中的 DATABASE_URL",
        "重启后端服务（本地进程或 docker compose restart backend）",
        "启动后访问 /api/health 确认正常，并抽查关键业务数据",
    ]
    return {
        "target_backend": backend,
        "target_url_masked": masked,
        "steps": steps,
        "note": "迁移不会热切换当前进程连接；必须改配置并重启后才会使用目标库。",
    }


def migrate_database(
    source_url: str,
    target_url: str,
    *,
    dry_run: bool = False,
    mode: SyncMode = "upsert",
    ensure_schema: bool = True,
    verify: bool = True,
    log: Callable[[str], None] = print,
) -> dict:
    """执行一次完整迁移编排。"""
    if not source_url or not target_url:
        raise ValueError("source_url 与 target_url 均不能为空")
    if source_url.strip() == target_url.strip():
        raise ValueError("源库与目标库不能相同")

    source_backend = detect_backend(source_url)
    target_backend = detect_backend(target_url)
    log(f"源: {source_backend} ({mask_database_url(source_url)})")
    log(f"目标: {target_backend} ({mask_database_url(target_url)})")

    source_engine = create_engine_from_url(source_url)
    target_engine = create_engine_from_url(target_url)

    try:
        probe_engine(source_engine)
        log("源库连接成功")

        if dry_run:
            # 预览只要求源库可读；目标 URL 仅用于生成切换指引
            log("dry-run：跳过目标库连接与建表")
        else:
            if ensure_schema:
                try:
                    probe_engine(target_engine)
                    log("目标库连接成功")
                except Exception:
                    log("目标库暂不可用，将先尝试建表")
                ensure_target_schema(target_url, log=log)
                target_engine.dispose()
                target_engine = create_engine_from_url(target_url)
                probe_engine(target_engine)
            else:
                probe_engine(target_engine)
                log("目标库连接成功")

        sync_result = sync_databases(
            source_engine,
            target_engine,
            dry_run=dry_run,
            mode=mode,
            log=log,
        )

        verify_result = None
        if verify and not dry_run:
            log("开始行数校验 ...")
            verify_result = verify_row_counts(source_engine, target_engine, log=log)
        elif verify and dry_run:
            log("dry-run 跳过行数校验写入对比")

        instructions = switch_instructions(target_url)
        for step in instructions["steps"]:
            log(f"  → {step}")
        log(instructions["note"])

        return {
            "source_backend": source_backend,
            "target_backend": target_backend,
            "dry_run": dry_run,
            "mode": mode,
            "sync": sync_result,
            "verify": verify_result,
            "switch_instructions": instructions,
            "ok": sync_result.get("errors", 0) == 0
            and (verify_result is None or verify_result.get("ok", False) or dry_run),
        }
    finally:
        source_engine.dispose()
        target_engine.dispose()


def verify_databases(
    source_url: str,
    target_url: str,
    *,
    log: Callable[[str], None] = print,
) -> dict:
    source_engine = create_engine_from_url(source_url)
    target_engine = create_engine_from_url(target_url)
    try:
        probe_engine(source_engine)
        probe_engine(target_engine)
        return verify_row_counts(source_engine, target_engine, log=log)
    finally:
        source_engine.dispose()
        target_engine.dispose()
