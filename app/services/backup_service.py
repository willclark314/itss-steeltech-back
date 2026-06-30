"""数据库备份服务 —— 定时调度 + 手动触发 + 历史管理"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import threading
from datetime import datetime
from pathlib import Path

from flask import Flask

from steeltech_db.defaults import (
    BACKUP_CONFIG_KEY,
    DEFAULT_BACKUP_CONFIG,
    BackupConfig,
    normalize_backup_config,
)
from steeltech_db.extensions import db
from steeltech_db.models import BackupRecord, SystemSetting


class BackupService:
    """数据库备份服务 —— 单例模式，维护调度器生命周期。"""

    _lock = threading.Lock()
    _scheduler = None

    # ── 配置读写 ──

    @staticmethod
    def get_config() -> BackupConfig:
        row = SystemSetting.query.filter_by(key=BACKUP_CONFIG_KEY).first()
        if row and row.value:
            try:
                parsed = json.loads(row.value)
                return normalize_backup_config(parsed)
            except (TypeError, json.JSONDecodeError):
                pass
        return BackupConfig()

    @staticmethod
    def get_config_dict() -> dict:
        return BackupService.get_config().to_dict()

    @staticmethod
    def _get_backup_root(app: Flask) -> Path:
        config = BackupService.get_config()
        root = Path(app.root_path).parent / config.backup_dir
        root.mkdir(parents=True, exist_ok=True)
        return root

    # ── 备份执行 ──

    def backup_now(self, app: Flask, trigger_type: str = "manual") -> BackupRecord:
        """执行一次数据库备份。"""
        with self._lock:
            config = self.get_config()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_dir = self._get_backup_root(app)

            record = BackupRecord(
                filename="",
                file_size=0,
                status="success",
                trigger_type=trigger_type,
                created_at=datetime.now(),
            )

            db_backend = app.config.get("DATABASE_BACKEND", "sqlite")
            error_msg: str | None = None

            try:
                if db_backend == "sqlite":
                    record.filename = f"backup_{timestamp}.db"
                    backup_path = backup_dir / record.filename
                    db_path = Path(app.config["SQLITE_DATABASE_PATH"])
                    shutil.copy2(db_path, backup_path)
                else:
                    record.filename = f"backup_{timestamp}.sql"
                    backup_path = backup_dir / record.filename
                    self._dump_mysql(app, backup_path)

                record.file_size = backup_path.stat().st_size

            except Exception as exc:
                record.status = "failed"
                error_msg = str(exc)
                record.error_message = error_msg

            db.session.add(record)
            db.session.commit()

            if record.status == "success":
                self._cleanup_old_backups(app, config)

            return record

    @staticmethod
    def _dump_mysql(app: Flask, backup_path: Path) -> None:
        """使用 mysqldump 导出 MySQL 数据库。"""
        uri = app.config["SQLALCHEMY_DATABASE_URI"]
        # 解析 mysql://user:pass@host:port/db
        from urllib.parse import urlparse

        parsed = urlparse(uri)
        host = parsed.hostname or "localhost"
        port = parsed.port or 3306
        user = parsed.username or ""
        password = parsed.password or ""
        database = parsed.path.lstrip("/")

        cmd = [
            "mysqldump",
            f"--host={host}",
            f"--port={port}",
            f"--user={user}",
            f"--password={password}",
            "--single-transaction",
            "--routines",
            "--triggers",
            database,
        ]

        with open(backup_path, "w", encoding="utf-8") as fp:
            subprocess.run(cmd, stdout=fp, stderr=subprocess.PIPE, check=True, timeout=300)

    # ── 清理旧备份 ──

    def _cleanup_old_backups(self, app: Flask, config: BackupConfig) -> None:
        """保留最近 retention_count 份备份，删除超出部分。"""
        if config.retention_count <= 0:
            return

        backup_dir = self._get_backup_root(app)
        records = (
            BackupRecord.query
            .filter_by(status="success")
            .order_by(BackupRecord.created_at.desc())
            .all()
        )

        keep_count = max(config.retention_count, 1)
        for record in records[keep_count:]:
            file_path = backup_dir / record.filename
            if file_path.exists():
                try:
                    file_path.unlink()
                except OSError:
                    pass
            db.session.delete(record)

        if len(records) > keep_count:
            db.session.commit()

    # ── 调度器管理 ──

    def init_scheduler(self, app: Flask) -> None:
        """初始化备份调度器（应用启动时调用）。"""
        # 防止 Gunicorn 多 worker 重复启动
        if os.environ.get("BACKUP_SCHEDULER_ENABLED", "true") != "true":
            return
        if os.environ.get("GUNICORN_WORKER_ID", "0") != "0":
            return

        config = self.get_config()
        if not config.enabled:
            return

        try:
            from apscheduler.schedulers.background import BackgroundScheduler
        except ImportError:
            app.logger.warning("APScheduler 未安装，跳过备份调度器初始化")
            return

        self._scheduler = BackgroundScheduler(daemon=True)
        self._add_job_from_config(app, config)
        self._scheduler.start()
        app.logger.info("备份调度器已启动")

    def shutdown_scheduler(self) -> None:
        """停止备份调度器。"""
        if self._scheduler is not None:
            self._scheduler.shutdown(wait=False)
            self._scheduler = None

    def apply_config(self, app: Flask, config_data: dict) -> BackupConfig:
        """更新备份配置并重启调度器。"""
        normalized = normalize_backup_config(config_data)

        row = SystemSetting.query.filter_by(key=BACKUP_CONFIG_KEY).first()
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        value = json.dumps(normalized.to_dict(), ensure_ascii=False)

        if row is None:
            row = SystemSetting(key=BACKUP_CONFIG_KEY, value=value, updated_at=now)
            db.session.add(row)
        else:
            row.value = value
            row.updated_at = now

        db.session.commit()

        # 重启调度器
        self.shutdown_scheduler()

        if normalized.enabled:
            self._scheduler = None
            self.init_scheduler(app)

        return normalized

    def _add_job_from_config(self, app: Flask, config: BackupConfig) -> None:
        """根据配置添加 cron job。"""
        if self._scheduler is None:
            return

        try:
            hour, minute = config.time.split(":")
            hour_int = int(hour)
            minute_int = int(minute)
        except (ValueError, AttributeError):
            hour_int, minute_int = 2, 0

        schedule_map = {
            "daily": {"minute": minute_int, "hour": hour_int},
            "weekly": {"minute": minute_int, "hour": hour_int, "day_of_week": "sun"},
            "monthly": {"minute": minute_int, "hour": hour_int, "day": "1"},
        }
        cron_kwargs = schedule_map.get(config.schedule, schedule_map["daily"])

        from apscheduler.triggers.cron import CronTrigger

        def _scheduled_backup():
            """在应用上下文中执行定时备份。"""
            with app.app_context():
                self.backup_now(app, trigger_type="scheduled")

        self._scheduler.add_job(
            _scheduled_backup,
            CronTrigger(**cron_kwargs),
            id="db_backup_job",
            name="数据库定时备份",
            replace_existing=True,
            max_instances=1,
        )

    # ── 查询 ──

    @staticmethod
    def get_history(page: int = 1, per_page: int = 20) -> dict:
        query = BackupRecord.query.order_by(BackupRecord.created_at.desc())
        total = query.count()
        items = query.offset((page - 1) * per_page).limit(per_page).all()
        return {
            "items": [r.to_dict() for r in items],
            "total": total,
        }

    @staticmethod
    def delete_backup(record_id: int, app: Flask | None = None) -> None:
        record = BackupRecord.query.get_or_404(record_id)
        if app is not None:
            config = BackupService.get_config()
            backup_dir = Path(app.root_path).parent / config.backup_dir
            file_path = backup_dir / record.filename
            if file_path.exists():
                try:
                    file_path.unlink()
                except OSError:
                    pass
        db.session.delete(record)
        db.session.commit()
