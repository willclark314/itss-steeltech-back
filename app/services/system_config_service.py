from __future__ import annotations

import json
from datetime import datetime

from steeltech_db.defaults import (
    DEFAULT_LOCAL_WORK_PATH,
    DEFAULT_SERVER_IP,
    SETTINGS_KEY,
    LocalWorkPathConfig,
    normalize_archive_template_paths,
    normalize_ip_list,
    normalize_path_patterns,
)
from steeltech_db.extensions import db
from steeltech_db.models import SystemSetting


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


def get_local_work_path_config() -> dict:
    row = SystemSetting.query.filter_by(key=SETTINGS_KEY).first()
    if row and row.value:
        try:
            parsed = json.loads(row.value)
            return normalize_local_work_path_config(parsed).to_dict()
        except (TypeError, json.JSONDecodeError):
            pass
    return normalize_local_work_path_config(DEFAULT_LOCAL_WORK_PATH.to_dict()).to_dict()


def save_local_work_path_config(payload: dict) -> dict:
    local_work_path = payload.get("localWorkPath")
    if not isinstance(local_work_path, dict):
        raise ValueError("请求体格式错误")

    normalized = normalize_local_work_path_config(local_work_path).to_dict()
    row = SystemSetting.query.filter_by(key=SETTINGS_KEY).first()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    value = json.dumps(normalized, ensure_ascii=False)

    if row is None:
        row = SystemSetting(key=SETTINGS_KEY, value=value, updated_at=now)
        db.session.add(row)
    else:
        row.value = value
        row.updated_at = now

    db.session.commit()
    return normalized
