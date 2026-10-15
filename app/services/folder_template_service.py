from __future__ import annotations

import re
import shutil
from datetime import datetime
from pathlib import Path

from app.config import Config
from app.services.contact_service import (
    list_project_contact_material_files,
    list_project_jiagongdan_material_files,
)
from app.services.system_config_service import get_local_work_path_config
from app.utils.paths import build_full_path_with_ip, normalize_access_path, normalize_relative_path

FILES_DIR = Config.BASE_DIR / "datas" / "files"
DIRECTORY_README_TEMPLATE_FILE = FILES_DIR / "directory_readme.template.txt"
PACK_README_TEMPLATE_FILE = FILES_DIR / "pack_readme.template.txt"
IP_PATTERN = re.compile(r"^(\d{1,3}\.){3}\d{1,3}$")
MAIN_PROJECT_DIR_MARKERS = ("工程编号", "项目名称")
SPECIAL_TEMPLATE_MARKERS = ("变更通知单", "楼承板排版图")
FOLDER_NAME_NOISE_PATTERNS = (
    re.compile(r"^（空样板[!！]勿剪切）\s*"),
    re.compile(r"\s*【待安排@@】\(需排瓦&不排瓦\)(?:\(GJGJSK-[\d.]+版\))?"),
)
INVALID_ARCHIVE_FILE_NAME_CHARS = re.compile(r'[<>:"/\\|?*]')
JIAGONGDAN_MATERIALS_DIR = "1，甲供资料"
DESIGN_CONTACT_MATERIALS_SUBDIR = "1-联系单及甲供其他资料"
DETAIL_CONTACT_PRIMARY_SUBDIR = "1-设计蓝图及沟通记录/2-联系单"
DETAIL_CONTACT_SUPPLEMENT_SUBDIR = "1-设计蓝图及沟通记录/1-蓝图设计图及答疑单"

ARCHIVE_COPY_PROFILES: dict[str, dict] = {
    "design": {
        "label": "设计组项目目录",
        "nameTokens": {},
        "preserveSourceRoot": False,
        "directoryReadme": "目录说明.txt",
        "packReadme": "打包说明.txt",
        "packReadmePaths": [".", "06 归档"],
        "copyContactMaterials": True,
        "contactPrimarySubdir": DESIGN_CONTACT_MATERIALS_SUBDIR,
        "contactSupplementSubdir": DESIGN_CONTACT_MATERIALS_SUBDIR,
    },
    "detail": {
        "label": "细化组项目目录",
        "nameTokens": {
            "工程编号": "{projectNo}",
            "项目名称": "{projectName}",
            "工程名称": "{projectName}",
        },
        "createInnerProjectFolder": True,
        "unwrapMainProjectDir": True,
        "directoryReadme": "目录说明.txt",
        "packReadme": "打包说明.txt",
        "packReadmePaths": [".", "3-加工图及清单/8-清单"],
        "copyContactMaterials": True,
        "contactPrimarySubdir": DETAIL_CONTACT_PRIMARY_SUBDIR,
        "contactSupplementSubdir": DETAIL_CONTACT_SUPPLEMENT_SUBDIR,
    },
    "detailJiagongdan": {
        "label": "细化加工单项目目录",
        "nameTokens": {
            "工程编号": "{projectNo}",
            "项目名称": "{projectName}",
            "工程名称": "{projectName}",
        },
        "createInnerProjectFolder": False,
        "preserveMainProjectFolder": True,
        "unwrapMainProjectDir": False,
        "directoryReadme": "目录说明.txt",
        "packReadme": "打包说明.txt",
        "packReadmePaths": [".", "2，清单"],
        "jiagongdanMaterialsDir": JIAGONGDAN_MATERIALS_DIR,
        "copyJiagongdanContactMaterials": True,
    },
}

ARCHIVE_PROFILE_LABELS = {
    "design": "设计归档模板",
    "detail": "细化归档模板",
    "detailJiagongdan": "细化加工单归档模板",
}


class FolderTemplateError(ValueError):
    pass


def list_folder_templates() -> list[dict]:
    return [
        {
            "key": key,
            "name": str(profile.get("label") or key),
            "description": f"从全局配置的{ARCHIVE_PROFILE_LABELS.get(key, key)}路径复制",
        }
        for key, profile in ARCHIVE_COPY_PROFILES.items()
    ]


def _validate_ip(ip: str) -> str:
    trimmed = ip.strip()
    if not trimmed:
        raise FolderTemplateError("IP 不能为空")
    if not IP_PATTERN.fullmatch(trimmed):
        raise FolderTemplateError("IP 格式不正确")
    return trimmed


def _validate_relative_path(path: str) -> str:
    normalized = normalize_relative_path(path)
    if not normalized:
        raise FolderTemplateError("路径不能为空")
    if ".." in normalized.split("\\"):
        raise FolderTemplateError("路径不能包含 ..")
    return normalized


def resolve_target_full_path(
    path: str,
    ip: str | None = None,
) -> str:
    trimmed = (path or "").strip()
    if not trimmed:
        raise FolderTemplateError("路径不能为空")

    if trimmed.startswith("\\\\"):
        full_path = trimmed.replace("/", "\\")
        if ".." in full_path.split("\\"):
            raise FolderTemplateError("路径不能包含 ..")
        return full_path

    if re.match(r"^[A-Za-z]:[\\/]", trimmed):
        full_path = trimmed.replace("/", "\\")
        if ".." in full_path.split("\\"):
            raise FolderTemplateError("路径不能包含 ..")
        return full_path

    config = get_local_work_path_config()
    target_ip = _validate_ip(ip or str(config.get("ip", "")))
    relative_path = _validate_relative_path(trimmed)
    return build_full_path_with_ip(relative_path, target_ip)


def _sanitize_folder_name(name: str) -> str:
    result = str(name or "").strip()
    for pattern in FOLDER_NAME_NOISE_PATTERNS:
        result = pattern.sub("", result)
    return result.strip().rstrip("/\\")


def _render_text(value: str, variables: dict[str, str]) -> str:
    rendered = value
    for key, raw in variables.items():
        rendered = rendered.replace(f"{{{key}}}", raw)
    return rendered


def _build_variables(payload: dict | None) -> dict[str, str]:
    defaults = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "datetime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "projectNo": "",
        "projectNoDigits": "",
        "projectName": "",
        "projectFolder": "",
    }
    if not payload:
        return defaults

    for key in ("projectNo", "projectNoDigits", "projectName", "projectFolder", "date", "datetime"):
        value = payload.get(key)
        if value is not None:
            defaults[key] = str(value).strip()

    defaults["projectName"] = _sanitize_folder_name(defaults["projectName"])

    for key, value in payload.items():
        if key in defaults or value is None:
            continue
        defaults[str(key)] = str(value).strip()

    if not defaults["projectFolder"]:
        project_no_digits = defaults["projectNoDigits"] or defaults["projectNo"]
        if defaults["projectName"]:
            defaults["projectFolder"] = f"{project_no_digits}#{defaults['projectName']}"
        else:
            defaults["projectFolder"] = project_no_digits
    else:
        defaults["projectFolder"] = _sanitize_folder_name(defaults["projectFolder"])

    return defaults


def _load_text_template(path: Path, fallback: str) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return fallback


def _translate_name(name: str, variables: dict[str, str], name_tokens: dict[str, str] | None) -> str:
    rendered = name
    if name_tokens:
        for token, pattern in name_tokens.items():
            rendered = rendered.replace(token, _render_text(str(pattern), variables))
    return _sanitize_folder_name(_render_text(rendered, variables))


def _is_main_project_dir(name: str) -> bool:
    if any(marker in name for marker in SPECIAL_TEMPLATE_MARKERS):
        return False
    return all(marker in name for marker in MAIN_PROJECT_DIR_MARKERS)


def _resolve_effective_template_source(source_root: Path) -> Path:
    """定位模板主项目目录：跳过变更通知单、楼承板排版图，并展开套娃样板层。"""
    current = source_root
    while current.is_dir():
        children = sorted(
            [item for item in current.iterdir() if item.is_dir()],
            key=lambda item: item.name.lower(),
        )
        if not children:
            break

        main_dirs = [item for item in children if _is_main_project_dir(item.name)]
        if len(main_dirs) == 1:
            current = main_dirs[0]
            continue

        if len(children) == 1 and _is_main_project_dir(children[0].name):
            current = children[0]
            continue

        break
    return current


def _build_directory_tree(root: Path, prefix: str = "") -> str:
    if not root.exists() or not root.is_dir():
        return "(空目录)\n"

    entries = sorted(root.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower()))
    visible_entries = [
        item for item in entries if item.name not in {"目录说明.txt", "打包说明.txt"}
    ]
    if not visible_entries:
        return "(空目录)\n"

    lines: list[str] = []
    count = len(visible_entries)
    for index, item in enumerate(visible_entries):
        connector = "└── " if index == count - 1 else "├── "
        if item.is_dir():
            lines.append(f"{prefix}{connector}{item.name}/")
            extension = "    " if index == count - 1 else "│   "
            child_tree = _build_directory_tree(item, prefix + extension)
            if child_tree.strip() and child_tree.strip() != "(空目录)":
                lines.append(child_tree.rstrip("\n"))
        else:
            lines.append(f"{prefix}{connector}{item.name}")
    return "\n".join(lines) + "\n"


def _write_text_file(
    target: Path,
    content: str,
    skip_existing: bool,
    created_files: list[str],
    skipped_files: list[str],
) -> None:
    if target.exists():
        if skip_existing:
            skipped_files.append(str(target))
            return
        if target.is_dir():
            raise FolderTemplateError(f"文件位置已被目录占用: {target.name}")

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    created_files.append(str(target))


def _write_directory_readme(
    directory: Path,
    project_root: Path,
    variables: dict[str, str],
    template: dict,
    skip_existing: bool,
    created_files: list[str],
    skipped_files: list[str],
) -> None:
    readme_name = str(template.get("directoryReadme") or "目录说明.txt").strip()
    if not readme_name:
        return

    relative_path = directory.relative_to(project_root).as_posix()
    if relative_path == ".":
        relative_path = "."

    readme_template = _load_text_template(
        DIRECTORY_README_TEMPLATE_FILE,
        "【目录说明】\n\n创建时间：{datetime}\n\n本目录结构：\n{directoryTree}\n",
    )
    content = _render_text(readme_template, {
        **variables,
        "dirName": directory.name,
        "relativePath": relative_path.replace("/", "\\"),
        "directoryTree": _build_directory_tree(directory).rstrip(),
    })
    _write_text_file(
        directory / readme_name,
        content,
        skip_existing,
        created_files,
        skipped_files,
    )


def _write_pack_readme_files(
    project_root: Path,
    variables: dict[str, str],
    template: dict,
    skip_existing: bool,
    created_files: list[str],
    skipped_files: list[str],
) -> None:
    readme_name = str(template.get("packReadme") or "打包说明.txt").strip()
    if not readme_name:
        return

    pack_paths = template.get("packReadmePaths")
    if not isinstance(pack_paths, list) or not pack_paths:
        pack_paths = ["."]

    pack_template = _load_text_template(
        PACK_README_TEMPLATE_FILE,
        "【打包说明】\n\n打包时间：\n打包目的：\n",
    )

    for raw_path in pack_paths:
        relative = str(raw_path or ".").strip()
        target_dir = _join_project_relative(project_root, relative)
        if not target_dir.exists():
            target_dir.mkdir(parents=True, exist_ok=True)

        content = _render_text(pack_template, {
            **variables,
            "dirName": target_dir.name,
            "relativePath": (
                "."
                if target_dir == project_root
                else target_dir.relative_to(project_root).as_posix().replace("/", "\\")
            ),
        })
        _write_text_file(
            target_dir / readme_name,
            content,
            skip_existing,
            created_files,
            skipped_files,
        )


def _ensure_directory(
    target: Path,
    skip_existing: bool,
    created_dirs: list[str],
    skipped_dirs: list[str],
) -> None:
    if target.exists():
        if target.is_dir():
            if skip_existing:
                skipped_dirs.append(str(target))
            return
        raise FolderTemplateError(f"目录位置已被文件占用: {target.name}")

    target.mkdir(parents=True, exist_ok=True)
    created_dirs.append(str(target))


def _copy_file(
    source: Path,
    target: Path,
    skip_existing: bool,
    created_files: list[str],
    skipped_files: list[str],
) -> None:
    if target.exists():
        if skip_existing:
            skipped_files.append(str(target))
            return
        if target.is_dir():
            raise FolderTemplateError(f"文件位置已被目录占用: {target.name}")

    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)
    created_files.append(str(target))


def _copy_source_entry(
    source: Path,
    target_root: Path,
    variables: dict[str, str],
    template: dict,
    skip_existing: bool,
    created_dirs: list[str],
    skipped_dirs: list[str],
    created_files: list[str],
    skipped_files: list[str],
) -> None:
    name_tokens = template.get("nameTokens") if isinstance(template.get("nameTokens"), dict) else {}
    unwrap_main = bool(template.get("unwrapMainProjectDir"))

    if source.is_dir() and unwrap_main and _is_main_project_dir(source.name):
        for child in sorted(source.iterdir(), key=lambda item: item.name.lower()):
            _copy_source_entry(
                child,
                target_root,
                variables,
                template,
                skip_existing,
                created_dirs,
                skipped_dirs,
                created_files,
                skipped_files,
            )
        return

    translated_name = _translate_name(source.name, variables, name_tokens)
    target = target_root / translated_name

    if source.is_dir():
        _ensure_directory(target, skip_existing, created_dirs, skipped_dirs)
        for child in sorted(source.iterdir(), key=lambda item: item.name.lower()):
            _copy_source_entry(
                child,
                target,
                variables,
                template,
                skip_existing,
                created_dirs,
                skipped_dirs,
                created_files,
                skipped_files,
            )
        return

    _copy_file(source, target, skip_existing, created_files, skipped_files)


def _is_jiagongdan(variables: dict[str, str]) -> bool:
    return str(variables.get("isJiagongdan") or "").strip().lower() in {"1", "true", "yes", "y"}


def _resolve_archive_profile_key(template_key: str, is_jiagongdan: bool) -> str:
    normalized = template_key.strip()
    if normalized == "design":
        return "design"
    if normalized == "detailJiagongdan":
        return "detailJiagongdan"
    if normalized == "detail" and is_jiagongdan:
        return "detailJiagongdan"
    return "detail"


def _resolve_archive_template_relative_path(config: dict, profile_key: str) -> str:
    paths = config.get("archiveTemplatePaths")
    if not isinstance(paths, dict):
        return ""
    return normalize_relative_path(str(paths.get(profile_key) or "").strip())


def _build_inner_project_folder_name(variables: dict[str, str]) -> str:
    project_no = str(variables.get("projectNo") or "").strip()
    project_name = _sanitize_folder_name(str(variables.get("projectName") or ""))
    if project_name:
        return f"{project_no}#{project_name}"
    return project_no


def _sanitize_archive_file_name(name: str) -> str:
    cleaned = INVALID_ARCHIVE_FILE_NAME_CHARS.sub("_", str(name or "").strip())
    return cleaned or "file"


def _unique_target_file(directory: Path, file_name: str) -> Path:
    safe_name = _sanitize_archive_file_name(file_name)
    target = directory / safe_name
    if not target.exists():
        return target

    stem = Path(safe_name).stem
    suffix = Path(safe_name).suffix
    index = 2
    while True:
        candidate = directory / f"{stem} ({index}){suffix}"
        if not candidate.exists():
            return candidate
        index += 1


def _resolve_jiagongdan_materials_dir(managed_root: Path, profile: dict) -> Path:
    preferred = str(profile.get("jiagongdanMaterialsDir") or JIAGONGDAN_MATERIALS_DIR).strip()
    preferred_path = managed_root / preferred
    if preferred_path.is_dir():
        return preferred_path

    for child in sorted(managed_root.iterdir(), key=lambda item: item.name.lower()):
        if child.is_dir() and "甲供资料" in child.name:
            return child

    preferred_path.mkdir(parents=True, exist_ok=True)
    return preferred_path


def _join_project_relative(project_root: Path, relative_path: str) -> Path:
    """Join a Windows-or-POSIX relative path onto project_root (safe on Linux mounts)."""
    normalized = str(relative_path or "").strip().replace("\\", "/").strip("/")
    if not normalized or normalized == ".":
        return project_root
    result = project_root
    for part in normalized.split("/"):
        if not part or part == ".":
            continue
        if part == "..":
            raise FolderTemplateError("路径不能包含 ..")
        result = result / part
    return result


def _resolve_profile_subdir(project_root: Path, relative_path: str) -> Path:
    return _join_project_relative(project_root, relative_path)


def _copy_project_contact_materials(
    project_root: Path,
    profile: dict,
    variables: dict[str, str],
    skip_existing: bool,
    created_dirs: list[str],
    skipped_dirs: list[str],
    created_files: list[str],
    skipped_files: list[str],
) -> None:
    project_no = str(variables.get("projectNo") or "").strip()
    if not project_no:
        return

    if bool(profile.get("copyJiagongdanContactMaterials")):
        materials = list_project_jiagongdan_material_files(project_no)
        if not materials:
            return
        target_dir = _resolve_jiagongdan_materials_dir(project_root, profile)
        if not target_dir.exists():
            _ensure_directory(target_dir, skip_existing, created_dirs, skipped_dirs)
        for item in materials:
            source = item["sourcePath"]
            if not isinstance(source, Path) or not source.is_file():
                continue
            target = _unique_target_file(target_dir, str(item.get("fileName") or source.name))
            _copy_file(source, target, skip_existing, created_files, skipped_files)
        return

    if not bool(profile.get("copyContactMaterials")):
        return

    materials = list_project_contact_material_files(project_no)
    if not materials:
        return

    primary_subdir = str(
        profile.get("contactPrimarySubdir") or DETAIL_CONTACT_PRIMARY_SUBDIR
    ).strip()
    supplement_subdir = str(
        profile.get("contactSupplementSubdir") or DETAIL_CONTACT_SUPPLEMENT_SUBDIR
    ).strip()

    for item in materials:
        source = item["sourcePath"]
        if not isinstance(source, Path) or not source.is_file():
            continue

        attachment_type = str(item.get("attachmentType") or "").strip()
        if attachment_type == "primary":
            relative_dir = primary_subdir
        else:
            relative_dir = supplement_subdir

        target_dir = _resolve_profile_subdir(project_root, relative_dir)
        if not target_dir.exists():
            _ensure_directory(target_dir, skip_existing, created_dirs, skipped_dirs)

        target = _unique_target_file(target_dir, str(item.get("fileName") or source.name))
        _copy_file(source, target, skip_existing, created_files, skipped_files)


def _collect_jiagongdan_copy_entries(source_root: Path) -> tuple[Path, list[Path]]:
    """甲供模板保留主项目目录名（含【甲供】等后缀），并复制同层的变更通知单等样板。"""
    effective_main = _resolve_effective_template_source(source_root)
    resolved_source = source_root.resolve()
    if effective_main.resolve() == resolved_source:
        return effective_main, []

    parent = effective_main.parent
    try:
        parent.relative_to(resolved_source)
    except ValueError:
        return effective_main, []

    siblings = [
        item for item in sorted(parent.iterdir(), key=lambda item: item.name.lower())
        if item != effective_main and item.is_dir()
    ]
    return effective_main, siblings


def _generate_from_archive_template(
    source_root: Path,
    project_root: Path,
    profile: dict,
    variables: dict[str, str],
    skip_existing: bool,
    created_dirs: list[str],
    skipped_dirs: list[str],
    created_files: list[str],
    skipped_files: list[str],
) -> Path:
    name_tokens = profile.get("nameTokens") if isinstance(profile.get("nameTokens"), dict) else {}
    preserve_main_folder = bool(profile.get("preserveMainProjectFolder"))
    pseudo_template = {
        "nameTokens": name_tokens,
        "preserveSourceRoot": False,
        "unwrapMainProjectDir": False if preserve_main_folder else bool(profile.get("unwrapMainProjectDir")),
        "directoryReadme": profile.get("directoryReadme"),
        "packReadme": profile.get("packReadme"),
        "packReadmePaths": profile.get("packReadmePaths"),
    }

    if preserve_main_folder:
        effective_main, sibling_dirs = _collect_jiagongdan_copy_entries(source_root)
        _copy_source_entry(
            effective_main,
            project_root,
            variables,
            pseudo_template,
            skip_existing,
            created_dirs,
            skipped_dirs,
            created_files,
            skipped_files,
        )
        for sibling in sibling_dirs:
            _copy_source_entry(
                sibling,
                project_root,
                variables,
                pseudo_template,
                skip_existing,
                created_dirs,
                skipped_dirs,
                created_files,
                skipped_files,
            )
        translated_main_name = _translate_name(effective_main.name, variables, name_tokens)
        managed_root = project_root / translated_main_name
        if not managed_root.exists():
            managed_root = project_root
    elif bool(profile.get("createInnerProjectFolder")):
        inner_name = _build_inner_project_folder_name(variables)
        if not inner_name:
            raise FolderTemplateError("无法生成内层项目文件夹名称")
        managed_root = project_root / inner_name
        _ensure_directory(managed_root, skip_existing, created_dirs, skipped_dirs)
        copy_target = managed_root
        effective_source = _resolve_effective_template_source(source_root)
        for child in sorted(effective_source.iterdir(), key=lambda item: item.name.lower()):
            _copy_source_entry(
                child,
                copy_target,
                variables,
                pseudo_template,
                skip_existing,
                created_dirs,
                skipped_dirs,
                created_files,
                skipped_files,
            )
    else:
        managed_root = project_root
        effective_source = _resolve_effective_template_source(source_root)
        for child in sorted(effective_source.iterdir(), key=lambda item: item.name.lower()):
            _copy_source_entry(
                child,
                project_root,
                variables,
                pseudo_template,
                skip_existing,
                created_dirs,
                skipped_dirs,
                created_files,
                skipped_files,
            )

    # 目录说明仅写在项目根目录，不向各子目录扩散
    _write_directory_readme(
        managed_root,
        managed_root,
        variables,
        pseudo_template,
        skip_existing,
        created_files,
        skipped_files,
    )

    _write_pack_readme_files(
        managed_root,
        variables,
        pseudo_template,
        skip_existing,
        created_files,
        skipped_files,
    )

    if bool(profile.get("copyJiagongdanContactMaterials")) or bool(profile.get("copyContactMaterials")):
        _copy_project_contact_materials(
            managed_root,
            profile,
            variables,
            skip_existing,
            created_dirs,
            skipped_dirs,
            created_files,
            skipped_files,
        )

    return managed_root


def generate_folder_structure(payload: dict) -> dict:
    template_key = str(payload.get("template") or payload.get("templateKey") or "").strip()
    if not template_key:
        raise FolderTemplateError("模板不能为空")

    full_path = resolve_target_full_path(
        str(payload.get("path") or ""),
        ip=str(payload.get("ip") or "").strip() or None,
    )
    skip_existing = payload.get("skipExisting")
    if skip_existing is None:
        skip_existing = not bool(payload.get("overwrite"))
    skip_existing = bool(skip_existing)

    variables = _build_variables(payload.get("variables") if isinstance(payload.get("variables"), dict) else None)
    profile_key = _resolve_archive_profile_key(template_key, _is_jiagongdan(variables))
    profile = ARCHIVE_COPY_PROFILES.get(profile_key)
    if not isinstance(profile, dict):
        raise FolderTemplateError(f"未找到模板: {template_key}")

    config = get_local_work_path_config()
    template_relative_path = _resolve_archive_template_relative_path(config, profile_key)
    if not template_relative_path:
        label = ARCHIVE_PROFILE_LABELS.get(profile_key, profile_key)
        raise FolderTemplateError(f"未配置{label}路径，请先在全局配置中设置")

    template_full_path = resolve_target_full_path(
        template_relative_path,
        ip=str(payload.get("ip") or "").strip() or None,
    )
    source_root = Path(normalize_access_path(template_full_path))
    if not source_root.exists() or not source_root.is_dir():
        raise FolderTemplateError(f"归档模板目录不存在: {template_full_path}")

    created_dirs: list[str] = []
    skipped_dirs: list[str] = []
    created_files: list[str] = []
    skipped_files: list[str] = []

    root = Path(normalize_access_path(full_path))
    if root.exists() and not root.is_dir():
        raise FolderTemplateError("目标路径已存在且不是文件夹")

    try:
        _ensure_directory(root, skip_existing, created_dirs, skipped_dirs)
    except OSError as exc:
        raise FolderTemplateError(f"创建目标目录失败: {exc}") from exc

    _generate_from_archive_template(
        source_root,
        root,
        profile,
        variables,
        skip_existing,
        created_dirs,
        skipped_dirs,
        created_files,
        skipped_files,
    )

    return {
        "ok": True,
        "template": profile_key,
        "fullPath": full_path,
        "templatePath": template_full_path,
        "createdDirs": created_dirs,
        "skippedDirs": skipped_dirs,
        "createdFiles": created_files,
        "skippedFiles": skipped_files,
    }
