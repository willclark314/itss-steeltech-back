from __future__ import annotations

import os
import re
from datetime import datetime

from steeltech_db.project_split import has_hyphen_split_suffix, parse_base_project_no

from app.services.system_config_service import get_local_work_path_config
from app.utils.paths import build_full_path, normalize_access_path, normalize_relative_path

_DETAIL_ARCHIVE_TEMPLATE = "f\\1【项目归档】深化组\\【{year}】深化组归档"
_JIAGONGDAN_ARCHIVE_TEMPLATE = "f\\1【项目归档】深化组\\【{year}】加工单归档（甲供）"
_DESIGN_ARCHIVE_TEMPLATE = "e\\【项目归档】设计组\\【{year}年】"


def extract_project_no_digits(project_no: str) -> str:
    trimmed = (project_no or "").strip()
    without_prefix = re.sub(r"^[A-Za-z]+", "", trimmed)
    if without_prefix and without_prefix.isdigit():
        return without_prefix
    digits = re.sub(r"\D", "", trimmed)
    return digits or trimmed


def extract_five_digit_project_no(project_no: str) -> str:
    digits = extract_project_no_digits(project_no)
    if len(digits) >= 5:
        return digits[-5:]
    return digits


def extract_project_year(project_no: str) -> str:
    digits = extract_project_no_digits(project_no)
    if len(digits) >= 2:
        return f"20{digits[:2]}"
    return str(datetime.now().year)


def _extract_year_from_relative_path(relative_path: str) -> str | None:
    match = re.search(r"【(\d{4})年?】", relative_path or "")
    return match.group(1) if match else None


def _extract_year_from_date(value: str) -> str | None:
    stored = (value or "").strip()
    if len(stored) >= 4 and stored[:4].isdigit():
        return stored[:4]
    return None


def _extract_year_from_jiagongdan_contact_id(contact_id: str) -> str | None:
    match = re.match(r"^BRD(\d{2})\d{4}C", (contact_id or "").strip(), re.IGNORECASE)
    if match:
        return f"20{match.group(1)}"
    return None


def _resolve_archive_year(
    received_date: str,
    relative_path: str,
    project_no: str,
    *,
    contact_form_ids: list[str] | None = None,
    is_jiagongdan: bool = False,
) -> str:
    if is_jiagongdan:
        for contact_id in contact_form_ids or []:
            year = _extract_year_from_jiagongdan_contact_id(contact_id)
            if year:
                return year

    year_from_date = _extract_year_from_date(received_date)
    if year_from_date:
        return year_from_date

    year_from_path = _extract_year_from_relative_path(relative_path)
    if year_from_path:
        return year_from_path

    return extract_project_year(project_no)


def _resolve_received_year(
    received_date: str,
    relative_path: str,
    project_no: str,
    *,
    contact_form_ids: list[str] | None = None,
    is_jiagongdan: bool = False,
) -> str:
    return _resolve_archive_year(
        received_date,
        relative_path,
        project_no,
        contact_form_ids=contact_form_ids,
        is_jiagongdan=is_jiagongdan,
    )


def _infer_is_jiagongdan(
    *,
    relative_path: str = "",
    project_name: str = "",
    contact_form_ids: list[str] | None = None,
    explicit: bool | None = None,
) -> bool:
    if explicit is not None:
        return explicit

    normalized = normalize_relative_path(relative_path)
    if "加工单归档" in normalized:
        return True

    if "加工单" in (project_name or ""):
        return True

    if "甲供" in (project_name or ""):
        return True

    for contact_id in contact_form_ids or []:
        if (contact_id or "").startswith("加工单-"):
            return True
        if (contact_id or "").strip() == "加工单":
            return True
        if re.match(r"^BRD\d{6}C\d{9}$", (contact_id or "").strip(), re.IGNORECASE):
            return True

    return False


def extract_path_match_key(project_no: str) -> str:
    """用于文件夹名匹配：AB25059-1 → 25059-1，AB25059 → 25059。"""
    trimmed = parse_base_project_no(project_no)
    without_prefix = re.sub(r"^[A-Za-z]+", "", trimmed)
    hyphen_match = re.fullmatch(r"(\d+-\d+)", without_prefix)
    if hyphen_match:
        return hyphen_match.group(1)
    if without_prefix and without_prefix.isdigit():
        return without_prefix
    digits = re.sub(r"\D", "", without_prefix)
    return digits or trimmed


def _folder_matches_project(folder_name: str, project_no: str) -> bool:
    base_no = parse_base_project_no(project_no)
    base_upper = base_no.upper()
    folder_upper = folder_name.upper()

    if has_hyphen_split_suffix(project_no):
        if base_upper in folder_upper:
            return True
        match_key = extract_path_match_key(project_no)
        return bool(match_key) and match_key in folder_name

    if base_upper in folder_upper:
        return True

    five_digits = extract_five_digit_project_no(project_no)
    if not five_digits or five_digits not in folder_name:
        return False

    if re.search(rf"{re.escape(five_digits)}-\d+", folder_name) and base_upper not in folder_upper:
        return False
    return True


def _score_folder(folder_name: str, project_no: str) -> int:
    base_no = parse_base_project_no(project_no)
    base_upper = base_no.upper()
    folder_upper = folder_name.upper()
    five_digits = extract_five_digit_project_no(project_no)

    if has_hyphen_split_suffix(project_no):
        match_key = extract_path_match_key(project_no)
        if folder_upper.startswith(f"{base_upper}#"):
            return 0
        if match_key and folder_name.startswith(f"{match_key}#"):
            return 1
        if base_upper in folder_upper:
            return 2
        if match_key and match_key in folder_name:
            return 3
        return 99

    if folder_name.startswith(f"{five_digits}#"):
        return 0
    if folder_name.startswith(five_digits):
        return 1
    if five_digits in folder_name:
        return 2
    return 99


def _resolve_archive_templates(
    natures: list[str] | None,
    relative_path: str,
    *,
    is_jiagongdan: bool,
) -> list[str]:
    unique = list(
        dict.fromkeys(
            item
            for item in (natures or [])
            if item in {
                "design",
                "detail",
                "detail_issue",
                "plate_layout",
                "floor_deck_layout",
                "tile_layout",
            }
        )
    )
    templates: list[str] = []

    if any(
        item in {"detail", "detail_issue", "plate_layout", "floor_deck_layout", "tile_layout"}
        for item in unique
    ):
        templates.append(
            _JIAGONGDAN_ARCHIVE_TEMPLATE if is_jiagongdan else _DETAIL_ARCHIVE_TEMPLATE
        )
    if "design" in unique:
        templates.append(_DESIGN_ARCHIVE_TEMPLATE)

    if templates:
        return templates

    normalized = normalize_relative_path(relative_path)
    if "深化" in normalized or "加工单归档" in normalized or is_jiagongdan:
        templates.append(
            _JIAGONGDAN_ARCHIVE_TEMPLATE
            if is_jiagongdan or "加工单归档" in normalized
            else _DETAIL_ARCHIVE_TEMPLATE
        )
    if "设计" in normalized:
        templates.append(_DESIGN_ARCHIVE_TEMPLATE)

    if templates:
        return templates

    return [
        _JIAGONGDAN_ARCHIVE_TEMPLATE if is_jiagongdan else _DETAIL_ARCHIVE_TEMPLATE,
        _DESIGN_ARCHIVE_TEMPLATE,
    ]


def _collect_archive_roots(
    config: dict,
    project_no: str,
    relative_path: str = "",
    natures: list[str] | None = None,
    *,
    received_date: str = "",
    contact_form_ids: list[str] | None = None,
    is_jiagongdan: bool = False,
) -> list[str]:
    """收集末级归档目录：深化/加工单在 f 盘，设计在 e 盘。"""
    year = _resolve_archive_year(
        received_date,
        relative_path,
        project_no,
        contact_form_ids=contact_form_ids,
        is_jiagongdan=is_jiagongdan,
    )
    templates = _resolve_archive_templates(
        natures,
        relative_path,
        is_jiagongdan=is_jiagongdan,
    )

    roots: list[str] = []
    for template in templates:
        relative = template.format(year=year)
        full_path = normalize_access_path(build_full_path(relative, config))
        if os.path.isdir(full_path) and relative not in roots:
            roots.append(relative)

    if roots:
        return roots

    ip = str(config.get("ip", "")).strip()
    if not ip:
        return roots

    for template in templates:
        relative = template.format(year=year)
        parent_relative = relative.rsplit("\\", 1)[0]
        parent_full = normalize_access_path(build_full_path(parent_relative, config))

        if not os.path.isdir(parent_full):
            continue

        archive_leaf = relative.rsplit("\\", 1)[-1]
        try:
            entries = os.listdir(parent_full)
        except OSError:
            continue

        for entry in entries:
            if entry != archive_leaf:
                continue
            candidate = f"{parent_relative}\\{entry}"
            if (
                os.path.isdir(normalize_access_path(build_full_path(candidate, config)))
                and candidate not in roots
            ):
                roots.append(candidate)

    return roots


def _full_path_to_relative(full_path: str, config: dict) -> str:
    ip = str(config.get("ip", "")).strip()
    normalized = full_path.replace("/", "\\")
    if ip:
        unc_prefix = f"\\\\{ip}\\"
        if normalized.lower().startswith(unc_prefix.lower()):
            rest = normalized[len(unc_prefix) :]
            share_match = re.match(r"^([A-Za-z])\\(.*)$", rest, re.IGNORECASE)
            if share_match and share_match.group(2) is not None:
                return normalize_relative_path(
                    f"{share_match.group(1).lower()}\\{share_match.group(2)}"
                )
        forward_prefix = f"//{ip}/"
        if full_path.lower().startswith(forward_prefix.lower()):
            rest = full_path[len(forward_prefix) :]
            share_match = re.match(r"^([A-Za-z])/(.*)$", rest, re.IGNORECASE)
            if share_match and share_match.group(2) is not None:
                rest_path = share_match.group(2).replace("/", "\\")
                return normalize_relative_path(
                    f"{share_match.group(1).lower()}\\{rest_path}"
                )
    return normalize_relative_path(normalized)


def _list_archive_folder_matches(archive_full_root: str, project_no: str) -> list[str]:
    """仅在末级归档目录的直接子文件夹中匹配项目号。"""
    if not archive_full_root or not os.path.isdir(archive_full_root):
        return []

    matches: list[str] = []
    try:
        with os.scandir(archive_full_root) as entries:
            for entry in entries:
                if not entry.is_dir(follow_symlinks=False):
                    continue
                if not _folder_matches_project(entry.name, project_no):
                    continue
                matches.append(entry.path)
    except OSError:
        return []

    return matches


def _normalize_relative_for_compare(relative_path: str) -> str:
    return normalize_relative_path(relative_path).rstrip("\\").lower()


def search_project_paths(
    project_no: str,
    relative_path: str = "",
    natures: list[str] | None = None,
    *,
    received_date: str = "",
    project_name: str = "",
    contact_form_ids: list[str] | None = None,
    is_jiagongdan: bool | None = None,
) -> list[dict]:
    project_no = (project_no or "").strip()
    if not project_no:
        return []

    five_digits = extract_five_digit_project_no(project_no)
    if not five_digits:
        return []

    resolved_is_jiagongdan = _infer_is_jiagongdan(
        relative_path=relative_path,
        project_name=project_name,
        contact_form_ids=contact_form_ids,
        explicit=is_jiagongdan,
    )

    config = get_local_work_path_config()
    current_relative = _normalize_relative_for_compare(relative_path)
    archive_roots = _collect_archive_roots(
        config,
        project_no,
        relative_path,
        natures,
        received_date=received_date,
        contact_form_ids=contact_form_ids,
        is_jiagongdan=resolved_is_jiagongdan,
    )

    found: dict[str, dict] = {}
    for root in archive_roots:
        full_root = normalize_access_path(build_full_path(root, config))
        for full_path in _list_archive_folder_matches(full_root, project_no):
            relative = _full_path_to_relative(full_path, config)
            if not relative:
                continue

            if _normalize_relative_for_compare(relative) == current_relative:
                continue

            folder_name = os.path.basename(full_path.rstrip("/\\"))
            score = _score_folder(folder_name, project_no)
            display_full_path = build_full_path(relative, config)
            existing = found.get(relative)
            if existing is None or score < existing["score"]:
                found[relative] = {
                    "relativePath": relative,
                    "fullPath": display_full_path,
                    "score": score,
                }

    return sorted(found.values(), key=lambda item: (item["score"], item["relativePath"]))[:5]
