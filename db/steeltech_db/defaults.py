"""系统配置默认值 —— 由 seed 模块和后端 system_config_service 共享。"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

DEFAULT_SERVER_IP = "10.10.1.175"
SETTINGS_KEY = "local_work_path"
BACKUP_CONFIG_KEY = "backup_config"

DEFAULT_PATH_PATTERNS = {
    "design": "e\\【项目归档】设计组\\【{year}年】\\{projectFolder}",
    "detailJiagongdan": "f\\1【项目归档】深化组\\【{year}】加工单归档（甲供）\\{projectFolder}",
    "detail": "f\\1【项目归档】深化组\\【{year}】深化组归档\\{projectFolder}",
}

DEFAULT_ARCHIVE_TEMPLATE_PATHS = {
    "design": "",
    "detailJiagongdan": "",
    "detail": "",
}


@dataclass
class LocalWorkPathConfig:
    ip: str = DEFAULT_SERVER_IP
    ips: list[str] | None = None
    path_patterns: dict[str, str] | None = None
    archive_template_paths: dict[str, str] | None = None
    suggest_path_on_mismatch: bool = False

    def to_dict(self) -> dict:
        ips = self.ips if self.ips is not None else [self.ip]
        patterns = self.path_patterns or DEFAULT_PATH_PATTERNS
        archive_templates = self.archive_template_paths or DEFAULT_ARCHIVE_TEMPLATE_PATHS
        return {
            "ip": self.ip,
            "ips": ips,
            "pathPatterns": {
                "design": str(patterns.get("design", DEFAULT_PATH_PATTERNS["design"])),
                "detailJiagongdan": str(
                    patterns.get("detailJiagongdan", DEFAULT_PATH_PATTERNS["detailJiagongdan"])
                ),
                "detail": str(patterns.get("detail", DEFAULT_PATH_PATTERNS["detail"])),
            },
            "archiveTemplatePaths": {
                "design": str(
                    archive_templates.get("design", DEFAULT_ARCHIVE_TEMPLATE_PATHS["design"])
                ),
                "detailJiagongdan": str(
                    archive_templates.get(
                        "detailJiagongdan",
                        DEFAULT_ARCHIVE_TEMPLATE_PATHS["detailJiagongdan"],
                    )
                ),
                "detail": str(
                    archive_templates.get("detail", DEFAULT_ARCHIVE_TEMPLATE_PATHS["detail"])
                ),
            },
            "suggestPathOnMismatch": bool(self.suggest_path_on_mismatch),
        }


DEFAULT_LOCAL_WORK_PATH = LocalWorkPathConfig(
    ip=DEFAULT_SERVER_IP,
    ips=[DEFAULT_SERVER_IP],
)


def normalize_ip_list(ips: list | None, fallback_ip: str = DEFAULT_SERVER_IP) -> list[str]:
    raw_list = ips if ips else [fallback_ip]
    seen: set[str] = set()
    result: list[str] = []

    for raw in raw_list:
        ip = str(raw).strip()
        if not ip or not re.fullmatch(r"(\d{1,3}\.){3}\d{1,3}", ip) or ip in seen:
            continue
        seen.add(ip)
        result.append(ip)

    if fallback_ip not in result:
        result.insert(0, fallback_ip)
    if not result:
        result.append(fallback_ip)
    return result


def normalize_path_patterns(patterns: dict | None) -> dict[str, str]:
    payload = patterns if isinstance(patterns, dict) else {}
    return {
        "design": str(payload.get("design", DEFAULT_PATH_PATTERNS["design"])).strip()
        or DEFAULT_PATH_PATTERNS["design"],
        "detailJiagongdan": str(
            payload.get("detailJiagongdan", DEFAULT_PATH_PATTERNS["detailJiagongdan"])
        ).strip()
        or DEFAULT_PATH_PATTERNS["detailJiagongdan"],
        "detail": str(payload.get("detail", DEFAULT_PATH_PATTERNS["detail"])).strip()
        or DEFAULT_PATH_PATTERNS["detail"],
    }


def normalize_archive_template_paths(paths: dict | None) -> dict[str, str]:
    payload = paths if isinstance(paths, dict) else {}
    return {
        "design": str(payload.get("design", DEFAULT_ARCHIVE_TEMPLATE_PATHS["design"])).strip(),
        "detailJiagongdan": str(
            payload.get("detailJiagongdan", DEFAULT_ARCHIVE_TEMPLATE_PATHS["detailJiagongdan"])
        ).strip(),
        "detail": str(payload.get("detail", DEFAULT_ARCHIVE_TEMPLATE_PATHS["detail"])).strip(),
    }


def normalize_local_work_path_config(config: dict | LocalWorkPathConfig | None) -> LocalWorkPathConfig:
    if config is None:
        return LocalWorkPathConfig(
            ip=DEFAULT_LOCAL_WORK_PATH.ip,
            ips=list(DEFAULT_LOCAL_WORK_PATH.ips or []),
        )

    if isinstance(config, LocalWorkPathConfig):
        payload = config.to_dict()
    else:
        payload = config

    ips = normalize_ip_list(
        payload.get("ips") if payload.get("ips") else [payload.get("ip", DEFAULT_SERVER_IP)],
    )
    ip_candidate = str(payload.get("ip", ips[0])).strip()
    ip = ip_candidate if ip_candidate in ips else ips[0]

    path_patterns = normalize_path_patterns(payload.get("pathPatterns"))
    archive_template_paths = normalize_archive_template_paths(payload.get("archiveTemplatePaths"))
    suggest_path_on_mismatch = bool(payload.get("suggestPathOnMismatch", False))

    return LocalWorkPathConfig(
        ip=ip,
        ips=ips,
        path_patterns=path_patterns,
        archive_template_paths=archive_template_paths,
        suggest_path_on_mismatch=suggest_path_on_mismatch,
    )


# ── 数据库备份配置 ──


@dataclass
class BackupConfig:
    enabled: bool = True
    schedule: str = "daily"         # daily / weekly / monthly
    time: str = "02:00"             # HH:MM 24h
    retention_count: int = 30
    backup_dir: str = "datas/backups"
    include_files: bool = True      # 同时备份联系单 PDF 等上传文件

    def to_dict(self) -> dict:
        return {
            "enabled": self.enabled,
            "schedule": self.schedule,
            "time": self.time,
            "retention_count": self.retention_count,
            "backup_dir": self.backup_dir,
            "include_files": self.include_files,
        }


DEFAULT_BACKUP_CONFIG = BackupConfig()


def normalize_backup_config(config: dict | BackupConfig | None) -> BackupConfig:
    if config is None:
        return BackupConfig()

    if isinstance(config, BackupConfig):
        payload = config.to_dict()
    else:
        payload = config

    return BackupConfig(
        enabled=bool(payload.get("enabled", True)),
        schedule=str(payload.get("schedule", "daily")).strip() or "daily",
        time=str(payload.get("time", "02:00")).strip() or "02:00",
        retention_count=int(payload.get("retention_count", 30)) or 30,
        backup_dir=str(payload.get("backup_dir", "datas/backups")).strip() or "datas/backups",
        include_files=bool(payload.get("include_files", True)),
    )
