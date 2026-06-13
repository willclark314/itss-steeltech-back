from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime

from app.extensions import db
from app.models import SystemSetting

DEFAULT_SERVER_IP = "10.10.1.175"
SETTINGS_KEY = "local_work_path"


DEFAULT_PATH_PATTERNS = {
    "design": "e\\itss\\{year}\\{projectNoDigits}#{projectName}",
    "detail": "f\\itss\\{year}\\{projectNoDigits}#{projectName}",
}


@dataclass
class LocalWorkPathConfig:
    ip: str = DEFAULT_SERVER_IP
    ips: list[str] | None = None
    drive: str = "F"
    path_patterns: dict[str, str] | None = None

    def to_dict(self) -> dict:
        ips = self.ips if self.ips is not None else [self.ip]
        patterns = self.path_patterns or DEFAULT_PATH_PATTERNS
        return {
            "ip": self.ip,
            "ips": ips,
            "drive": self.drive,
            "pathPatterns": {
                "design": str(patterns.get("design", DEFAULT_PATH_PATTERNS["design"])),
                "detail": str(patterns.get("detail", DEFAULT_PATH_PATTERNS["detail"])),
            },
        }


DEFAULT_LOCAL_WORK_PATH = LocalWorkPathConfig(
    ip=DEFAULT_SERVER_IP,
    ips=[DEFAULT_SERVER_IP],
    drive="F",
)


def normalize_drive(drive: str) -> str:
    return drive.replace(":", "").strip().upper()


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
        "detail": str(payload.get("detail", DEFAULT_PATH_PATTERNS["detail"])).strip()
        or DEFAULT_PATH_PATTERNS["detail"],
    }


def normalize_local_work_path_config(config: dict | LocalWorkPathConfig | None) -> LocalWorkPathConfig:
    if config is None:
        return LocalWorkPathConfig(
            ip=DEFAULT_LOCAL_WORK_PATH.ip,
            ips=list(DEFAULT_LOCAL_WORK_PATH.ips or []),
            drive=DEFAULT_LOCAL_WORK_PATH.drive,
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
    drive = normalize_drive(str(payload.get("drive", DEFAULT_LOCAL_WORK_PATH.drive)))

    path_patterns = normalize_path_patterns(payload.get("pathPatterns"))

    return LocalWorkPathConfig(ip=ip, ips=ips, drive=drive, path_patterns=path_patterns)


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

    drive = str(local_work_path.get("drive", "")).strip()
    if not drive:
        raise ValueError("默认盘符不能为空")
    if not re.fullmatch(r"[A-Za-z]", drive):
        raise ValueError("盘符为单个字母")

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
