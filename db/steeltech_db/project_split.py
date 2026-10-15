"""项目号解析工具。业务项目号唯一对应 projects 一行，多联系单通过 contact_form_projects 关联。"""

from __future__ import annotations

import re

LEGACY_PROJECT_SPLIT_SEP = "#"
PROJECT_SPLIT_SEP = "~"
PROCESSING_CONTACT_LABEL = "加工单"
PROCESSING_CONTACT_PREFIX = "加工单-"
PROCESSING_BRD_PATTERN = re.compile(r"^BRD\d{6}C\d{9}$", re.IGNORECASE)
HYPHEN_SPLIT_PATTERN = re.compile(r"^(.*)-(\d+)$")


def is_processing_contact_id(contact_form_id: str) -> bool:
    normalized = (contact_form_id or "").strip()
    if not normalized:
        return False
    return (
        normalized == PROCESSING_CONTACT_LABEL
        or normalized.startswith(PROCESSING_CONTACT_PREFIX)
        or bool(PROCESSING_BRD_PATTERN.fullmatch(normalized))
    )


def parse_base_project_no(project_no: str) -> str:
    project_no = (project_no or "").strip()
    for sep in ("~", LEGACY_PROJECT_SPLIT_SEP):
        if sep in project_no:
            return project_no.split(sep, 1)[0]
    return project_no


def is_split_project_no(project_no: str) -> bool:
    project_no = project_no or ""
    return "~" in project_no or LEGACY_PROJECT_SPLIT_SEP in project_no


def parse_hyphen_root(project_no: str) -> str:
    """去除 ~/# 及 -N 后缀，得到短横线拆分的根项目号。"""
    text = parse_base_project_no(project_no)
    match = HYPHEN_SPLIT_PATTERN.match(text)
    return match.group(1) if match else text


def has_hyphen_split_suffix(project_no: str) -> bool:
    text = parse_base_project_no(project_no)
    return bool(HYPHEN_SPLIT_PATTERN.match(text))


def resolve_import_project_no(
    base_project_no: str,
    contact_form_id: str,
    *,
    base_primary_contact: dict[str, str] | None = None,
) -> str:
    """导入时始终使用业务项目号，多联系单通过关联表挂载。"""
    _ = contact_form_id, base_primary_contact
    return parse_base_project_no(base_project_no)
