from __future__ import annotations

import os
import re

from app.services.system_config_service import get_local_work_path_config


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


def infer_share_letter(relative_path: str) -> str:
    if "深化组" in relative_path or "加工单归档" in relative_path:
        return "f"
    if "设计组" in relative_path:
        return "e"
    return "f"


def build_full_path_with_ip(
    relative_path: str,
    ip: str,
    config: dict | None = None,
) -> str:
    normalized = normalize_relative_path(relative_path)
    if not normalized:
        return ""

    work_path = config or get_local_work_path_config()
    target_ip = str(ip or work_path.get("ip", "")).strip()

    share_prefix = re.match(r"^([A-Za-z])\\(.+)$", normalized, re.IGNORECASE)
    if share_prefix:
        return f"\\\\{target_ip}\\{share_prefix.group(1).lower()}\\{share_prefix.group(2)}"

    share = infer_share_letter(normalized)
    return f"\\\\{target_ip}\\{share}\\{normalized}"


def build_full_path(relative_path: str, config: dict | None = None) -> str:
    work_path = config or get_local_work_path_config()
    ip = str(work_path.get("ip", "")).strip()
    return build_full_path_with_ip(relative_path, ip, work_path)


def normalize_access_path(full_path: str) -> str:
    """将 UNC 路径转换为当前系统可访问的形式。

    - Windows 本机：\\\\ip\\share\\path → //ip/share/path（部分环境后者可访问）
    - Linux 容器：若设置 FILESERVER_MOUNT_ROOT（如 /mnt/archive），则
      \\\\ip\\f\\a\\b → /mnt/archive/f/a/b（对应 CIFS 挂载的共享盘符）
    """
    trimmed = (full_path or "").strip()
    if not trimmed:
        return ""

    mount_root = os.getenv("FILESERVER_MOUNT_ROOT", "").strip().rstrip("/\\")
    slash_path = trimmed.replace("\\", "/")
    if mount_root:
        # //ip/f/rest 或 //ip/f
        unc_match = re.match(r"^//[^/]+/([A-Za-z])(?:/(.*))?$", slash_path)
        if unc_match:
            share = unc_match.group(1).lower()
            rest = (unc_match.group(2) or "").strip("/")
            return f"{mount_root}/{share}/{rest}" if rest else f"{mount_root}/{share}"

    if trimmed.startswith("\\\\") or slash_path.startswith("//"):
        return slash_path
    return trimmed
