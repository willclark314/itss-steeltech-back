from __future__ import annotations

import re

from app.services.system_config_service import get_local_work_path_config, normalize_drive


def normalize_relative_path(value: str) -> str:
    trimmed = (value or "").strip()
    if not trimmed:
        return ""

    unc_match = re.match(r"^\\\\[^\\]+\\([A-Za-z])\$?\\(.*)$", trimmed, re.IGNORECASE)
    if unc_match and unc_match.group(2) is not None:
        share = unc_match.group(1).lower()
        rest = unc_match.group(2).replace("/", "\\").lstrip("\\")
        return f"{share}\\{rest}" if rest else share

    ip_path_match = re.match(r"^[\d.]+\\([A-Za-z])\\(.*)$", trimmed, re.IGNORECASE)
    if ip_path_match and ip_path_match.group(2) is not None:
        share = ip_path_match.group(1).lower()
        rest = ip_path_match.group(2).replace("/", "\\").lstrip("\\")
        return f"{share}\\{rest}" if rest else share

    drive_match = re.match(r"^([A-Za-z]):[\\/]*(.*)$", trimmed, re.IGNORECASE)
    if drive_match and drive_match.group(1):
        share = drive_match.group(1).lower()
        rest = (drive_match.group(2) or "").replace("/", "\\").lstrip("\\")
        return f"{share}\\{rest}" if rest else share

    return trimmed.replace("/", "\\").lstrip("\\")


def infer_share_letter(relative_path: str, drive: str) -> str:
    if "深化组" in relative_path or "加工单归档" in relative_path:
        return "f"
    if "设计组" in relative_path:
        return "e"
    return normalize_drive(drive).lower()


def build_full_path_with_ip(
    relative_path: str,
    ip: str,
    drive: str = "F",
    config: dict | None = None,
) -> str:
    normalized = normalize_relative_path(relative_path)
    if not normalized:
        return ""

    work_path = config or get_local_work_path_config()
    target_ip = str(ip or work_path.get("ip", "")).strip()
    target_drive = normalize_drive(str(drive or work_path.get("drive", "F")))

    share_prefix = re.match(r"^([A-Za-z])\\(.+)$", normalized, re.IGNORECASE)
    if share_prefix:
        return f"\\\\{target_ip}\\{share_prefix.group(1).lower()}\\{share_prefix.group(2)}"

    share = infer_share_letter(normalized, target_drive)
    return f"\\\\{target_ip}\\{share}\\{normalized}"


def build_full_path(relative_path: str, config: dict | None = None) -> str:
    work_path = config or get_local_work_path_config()
    ip = str(work_path.get("ip", "")).strip()
    drive = normalize_drive(str(work_path.get("drive", "F")))
    return build_full_path_with_ip(relative_path, ip, drive, work_path)
