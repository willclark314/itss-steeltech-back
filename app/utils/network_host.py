from __future__ import annotations

import os
import re
import shutil
import socket
import subprocess
from dataclasses import dataclass


@dataclass
class HostDriveInfo:
    name: str
    label: str
    type: str
    total_bytes: int | None = None
    free_bytes: int | None = None

    def to_dict(self) -> dict:
        payload = {
            "name": self.name,
            "label": self.label,
            "type": self.type,
        }
        if self.total_bytes is not None:
            payload["totalBytes"] = self.total_bytes
        if self.free_bytes is not None:
            payload["freeBytes"] = self.free_bytes
        return payload


def get_local_ipv4_addresses() -> list[str]:
    ips: set[str] = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None):
            if info[0] == socket.AF_INET:
                address = info[4][0]
                if address and not address.startswith("127."):
                    ips.add(address)
    except OSError:
        pass

    if not ips and os.name == "nt":
        try:
            output = subprocess.check_output(["ipconfig"], text=True, encoding="utf-8", errors="ignore")
            for match in re.finditer(r"IPv4[^:]*:\s*(\d+\.\d+\.\d+\.\d+)", output):
                address = match.group(1)
                if not address.startswith("127."):
                    ips.add(address)
        except (OSError, subprocess.SubprocessError):
            pass

    return sorted(ips)


def is_local_host_ip(ip: str) -> bool:
    trimmed = ip.strip()
    if not trimmed or trimmed in {"127.0.0.1", "localhost"}:
        return True
    return trimmed in get_local_ipv4_addresses()


def _list_local_drive_letters() -> list[HostDriveInfo]:
    drives: list[HostDriveInfo] = []
    if os.name != "nt":
        return drives

    for code in range(65, 91):
        letter = chr(code)
        root = f"{letter}:\\"
        if os.path.exists(root):
            drives.append(HostDriveInfo(name=letter, label=f"{letter}:", type="local"))
    return drives


def _read_local_drive_space(letter: str) -> tuple[int | None, int | None]:
    if os.name != "nt":
        return None, None
    try:
        total, _used, free = shutil.disk_usage(f"{letter}:\\")
        return total, free
    except OSError:
        return None, None


def _list_local_drives_with_space() -> list[HostDriveInfo]:
    drives = _list_local_drive_letters()
    result: list[HostDriveInfo] = []
    for drive in drives:
        total_bytes, free_bytes = _read_local_drive_space(drive.name)
        result.append(
            HostDriveInfo(
                name=drive.name,
                label=drive.label,
                type=drive.type,
                total_bytes=total_bytes,
                free_bytes=free_bytes,
            )
        )
    return result


def _parse_net_view_shares(stdout: str) -> list[HostDriveInfo]:
    shares: list[HostDriveInfo] = []
    seen: set[str] = set()
    for line in stdout.splitlines():
        trimmed = line.strip()
        match = re.match(r"^(\S+)\s+(Disk|Print|IPC|Special)", trimmed, re.IGNORECASE)
        if not match:
            continue
        name = match.group(1)
        if name.endswith("$") or name.lower() in seen:
            continue
        seen.add(name.lower())
        shares.append(HostDriveInfo(name=name, label=name, type="share"))
    return shares


def _list_remote_shares(ip: str) -> list[HostDriveInfo]:
    if os.name == "nt":
        try:
            output = subprocess.check_output(
                ["net", "view", f"\\\\{ip}"],
                text=True,
                encoding="gbk",
                errors="ignore",
                timeout=15,
            )
            shares = _parse_net_view_shares(output)
            if shares:
                return shares
        except (OSError, subprocess.SubprocessError):
            pass
    return _probe_admin_shares(ip)


def _probe_admin_shares(ip: str) -> list[HostDriveInfo]:
    shares: list[HostDriveInfo] = []
    for code in range(65, 91):
        letter = chr(code)
        unc = f"\\\\{ip}\\{letter}$"
        if os.path.exists(unc):
            shares.append(HostDriveInfo(name=letter, label=f"{letter}$", type="share"))
    return shares


def list_host_drives(ip: str) -> dict:
    trimmed = ip.strip()
    if not trimmed:
        raise ValueError("IP 不能为空")
    if not re.fullmatch(r"(\d{1,3}\.){3}\d{1,3}", trimmed):
        raise ValueError("IP 格式不正确")

    is_local = is_local_host_ip(trimmed)
    drives = _list_local_drives_with_space() if is_local else _list_remote_shares(trimmed)
    return {
        "ip": trimmed,
        "isLocal": is_local,
        "drives": [drive.to_dict() for drive in drives],
    }
