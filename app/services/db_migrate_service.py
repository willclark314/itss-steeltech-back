"""数据库双向迁移服务 —— 预览 / 执行 / 校验（不热切换连接）。"""

from __future__ import annotations

import threading

from flask import Flask

from steeltech_db.database_url import detect_backend
from steeltech_db.db_migrate import (
    mask_database_url,
    migrate_database,
    switch_instructions,
    verify_databases,
)
from steeltech_db.db_sync import SyncMode


class DbMigrateService:
    """迁移服务 —— 进程内锁防止并发迁移。"""

    _lock = threading.Lock()

    @staticmethod
    def current_source_url(app: Flask) -> str:
        return str(app.config.get("SQLALCHEMY_DATABASE_URI") or "")

    @staticmethod
    def get_status(app: Flask) -> dict:
        source_url = DbMigrateService.current_source_url(app)
        backend = app.config.get("DATABASE_BACKEND") or (
            detect_backend(source_url) if source_url else "unknown"
        )
        suggested = "mysql" if backend == "sqlite" else "sqlite"
        return {
            "current_backend": backend,
            "current_url_masked": mask_database_url(source_url),
            "suggested_target_backend": suggested,
            "note": "迁移成功后请修改服务器 DATABASE_URL 并重启后端，不会热切换当前连接。",
        }

    def preview(self, app: Flask, target_url: str) -> dict:
        return self._run(
            app,
            target_url=target_url,
            dry_run=True,
            mode="upsert",
            backup_first=False,
            ensure_schema=False,
            verify=False,
        )

    def run(
        self,
        app: Flask,
        *,
        target_url: str,
        mode: SyncMode = "upsert",
        backup_first: bool = True,
    ) -> dict:
        return self._run(
            app,
            target_url=target_url,
            dry_run=False,
            mode=mode,
            backup_first=backup_first,
            ensure_schema=True,
            verify=True,
        )

    def verify(self, app: Flask, target_url: str) -> dict:
        source_url = self.current_source_url(app)
        if not target_url:
            raise ValueError("target_url 不能为空")
        logs: list[str] = []

        def log(msg: str) -> None:
            logs.append(msg)

        if not self._lock.acquire(blocking=False):
            raise RuntimeError("已有迁移任务在进行中，请稍后再试")
        try:
            result = verify_databases(source_url, target_url, log=log)
            return {
                "verify": result,
                "logs": logs,
                "switch_instructions": switch_instructions(target_url),
                "ok": bool(result.get("ok")),
            }
        finally:
            self._lock.release()

    def _run(
        self,
        app: Flask,
        *,
        target_url: str,
        dry_run: bool,
        mode: SyncMode,
        backup_first: bool,
        ensure_schema: bool,
        verify: bool,
    ) -> dict:
        source_url = self.current_source_url(app)
        if not source_url:
            raise ValueError("当前应用未配置 SQLALCHEMY_DATABASE_URI")
        target_url = (target_url or "").strip()
        if not target_url:
            raise ValueError("target_url 不能为空")
        detect_backend(target_url)  # validate

        if not self._lock.acquire(blocking=False):
            raise RuntimeError("已有迁移任务在进行中，请稍后再试")

        logs: list[str] = []

        def log(msg: str) -> None:
            logs.append(msg)
            app.logger.info("[db-migrate] %s", msg)

        backup_record = None
        try:
            if backup_first and not dry_run:
                from app.services.backup_service import BackupService

                log("迁移前先备份当前库 ...")
                record = BackupService().backup_now(app, trigger_type="manual")
                backup_dir = BackupService._get_backup_root(app)
                backup_record = BackupService.record_to_dict(record, backup_dir)
                if record.status != "success":
                    raise RuntimeError(
                        f"预备份失败: {record.error_message or record.status}"
                    )

            result = migrate_database(
                source_url,
                target_url,
                dry_run=dry_run,
                mode=mode,
                ensure_schema=ensure_schema,
                verify=verify,
                log=log,
            )
            result["logs"] = logs
            if backup_record is not None:
                result["backup"] = backup_record
            return result
        finally:
            self._lock.release()
