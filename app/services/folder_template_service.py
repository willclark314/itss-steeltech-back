from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path

from app.config import Config
from app.services.system_config_service import get_local_work_path_config, normalize_drive
from app.utils.paths import build_full_path_with_ip, normalize_relative_path

TEMPLATE_FILE = Config.BASE_DIR / "datas" / "project_folder_templates.json"
FILES_DIR = Config.BASE_DIR / "datas" / "files"
DIRECTORY_README_TEMPLATE_FILE = FILES_DIR / "directory_readme.template.txt"
PACK_README_TEMPLATE_FILE = FILES_DIR / "pack_readme.template.txt"
IP_PATTERN = re.compile(r"^(\d{1,3}\.){3}\d{1,3}$")
MAIN_PROJECT_DIR_MARKERS = ("工程编号", "项目名称")
SPECIAL_TEMPLATE_MARKERS = ("变更通知单", "楼承板排版图")


class FolderTemplateError(ValueError):
    pass


def _load_templates() -> dict[str, dict]:
    if not TEMPLATE_FILE.exists():
        raise FolderTemplateError("模板配置文件不存在")

    try:
        payload = json.loads(TEMPLATE_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise FolderTemplateError("模板配置文件格式错误") from exc

    if not isinstance(payload, dict):
        raise FolderTemplateError("模板配置文件格式错误")
    return payload


def list_folder_templates() -> list[dict]:
    templates = _load_templates()
    return [
        {
            "key": key,
            "name": str(item.get("name") or key),
            "description": str(item.get("description") or ""),
        }
        for key, item in templates.items()
        if isinstance(item, dict)
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
    drive: str | None = None,
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
    target_drive = normalize_drive(str(drive or config.get("drive", "F")))
    relative_path = _validate_relative_path(trimmed)
    return build_full_path_with_ip(relative_path, target_ip, target_drive)


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
    return _render_text(rendered, variables)


def _is_main_project_dir(name: str) -> bool:
    if any(marker in name for marker in SPECIAL_TEMPLATE_MARKERS):
        return False
    return all(marker in name for marker in MAIN_PROJECT_DIR_MARKERS)


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
        relative = str(raw_path or ".").strip().replace("/", "\\").strip("\\")
        target_dir = project_root if not relative or relative == "." else project_root / relative
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


def _generate_from_source(
    template: dict,
    project_root: Path,
    variables: dict[str, str],
    skip_existing: bool,
    created_dirs: list[str],
    skipped_dirs: list[str],
    created_files: list[str],
    skipped_files: list[str],
) -> None:
    source_dir = str(template.get("sourceDir") or "").strip()
    if not source_dir:
        raise FolderTemplateError("模板未配置 sourceDir")

    source_root_name = str(template.get("sourceRoot") or "").strip()
    source_base = FILES_DIR / source_dir.replace("/", "\\").strip("\\")
    source_root = source_base / source_root_name if source_root_name else source_base

    if not source_root.exists() or not source_root.is_dir():
        raise FolderTemplateError(f"模板源目录不存在: {source_root}")

    for child in sorted(source_root.iterdir(), key=lambda item: item.name.lower()):
        _copy_source_entry(
            child,
            project_root,
            variables,
            template,
            skip_existing,
            created_dirs,
            skipped_dirs,
            created_files,
            skipped_files,
        )

    managed_dirs = [path for path in project_root.rglob("*") if path.is_dir()]
    managed_dirs.append(project_root)
    managed_dirs.sort(key=lambda path: len(path.parts))

    for directory in managed_dirs:
        _write_directory_readme(
            directory,
            project_root,
            variables,
            template,
            skip_existing,
            created_files,
            skipped_files,
        )

    _write_pack_readme_files(
        project_root,
        variables,
        template,
        skip_existing,
        created_files,
        skipped_files,
    )


def _generate_from_directories(
    template: dict,
    project_root: Path,
    variables: dict[str, str],
    directories: list[str],
    files: list[dict],
    skip_existing: bool,
    created_dirs: list[str],
    skipped_dirs: list[str],
    created_files: list[str],
    skipped_files: list[str],
) -> None:
    for directory in directories:
        rendered_name = _render_text(directory, variables)
        target = project_root / rendered_name
        _ensure_directory(target, skip_existing, created_dirs, skipped_dirs)

    for file_item in files:
        rendered_path = _render_text(file_item["path"], variables)
        target = project_root / rendered_path
        content = _render_text(file_item["content"], variables)
        _write_text_file(target, content, skip_existing, created_files, skipped_files)

    managed_dirs = [path for path in project_root.rglob("*") if path.is_dir()]
    managed_dirs.append(project_root)
    managed_dirs.sort(key=lambda path: len(path.parts))

    for directory in managed_dirs:
        _write_directory_readme(
            directory,
            project_root,
            variables,
            template,
            skip_existing,
            created_files,
            skipped_files,
        )

    _write_pack_readme_files(
        project_root,
        variables,
        template,
        skip_existing,
        created_files,
        skipped_files,
    )


def _validate_template_item(template_key: str, template: dict) -> tuple[list[str], list[dict]]:
    if template.get("sourceDir"):
        return [], []

    directories = template.get("directories")
    files = template.get("files")

    if not isinstance(directories, list) or not directories:
        raise FolderTemplateError(f"模板 {template_key} 未配置目录")

    normalized_dirs: list[str] = []
    for item in directories:
        name = str(item).strip().replace("/", "\\").strip("\\")
        if not name:
            raise FolderTemplateError(f"模板 {template_key} 存在空目录名")
        if ".." in name.split("\\"):
            raise FolderTemplateError(f"模板 {template_key} 目录名不能包含 ..")
        normalized_dirs.append(name)

    normalized_files: list[dict] = []
    if files is None:
        return normalized_dirs, normalized_files
    if not isinstance(files, list):
        raise FolderTemplateError(f"模板 {template_key} 文件配置格式错误")

    for item in files:
        if not isinstance(item, dict):
            raise FolderTemplateError(f"模板 {template_key} 文件配置格式错误")
        relative_path = str(item.get("path", "")).strip().replace("/", "\\").strip("\\")
        if not relative_path:
            raise FolderTemplateError(f"模板 {template_key} 存在空文件路径")
        if ".." in relative_path.split("\\"):
            raise FolderTemplateError(f"模板 {template_key} 文件路径不能包含 ..")
        normalized_files.append(
            {
                "path": relative_path,
                "content": str(item.get("content", "")),
            }
        )

    return normalized_dirs, normalized_files


def generate_folder_structure(payload: dict) -> dict:
    template_key = str(payload.get("template") or payload.get("templateKey") or "").strip()
    if not template_key:
        raise FolderTemplateError("模板不能为空")

    templates = _load_templates()
    template = templates.get(template_key)
    if not isinstance(template, dict):
        raise FolderTemplateError(f"未找到模板: {template_key}")

    full_path = resolve_target_full_path(
        str(payload.get("path") or ""),
        ip=str(payload.get("ip") or "").strip() or None,
        drive=str(payload.get("drive") or "").strip() or None,
    )
    skip_existing = payload.get("skipExisting")
    if skip_existing is None:
        skip_existing = not bool(payload.get("overwrite"))
    skip_existing = bool(skip_existing)

    variables = _build_variables(payload.get("variables") if isinstance(payload.get("variables"), dict) else None)

    created_dirs: list[str] = []
    skipped_dirs: list[str] = []
    created_files: list[str] = []
    skipped_files: list[str] = []

    root = Path(full_path)
    if root.exists() and not root.is_dir():
        raise FolderTemplateError("目标路径已存在且不是文件夹")

    try:
        _ensure_directory(root, skip_existing, created_dirs, skipped_dirs)
    except OSError as exc:
        raise FolderTemplateError(f"创建目标目录失败: {exc}") from exc

    if template.get("sourceDir"):
        _generate_from_source(
            template,
            root,
            variables,
            skip_existing,
            created_dirs,
            skipped_dirs,
            created_files,
            skipped_files,
        )
    else:
        directories, files = _validate_template_item(template_key, template)
        _generate_from_directories(
            template,
            root,
            variables,
            directories,
            files,
            skip_existing,
            created_dirs,
            skipped_dirs,
            created_files,
            skipped_files,
        )

    return {
        "ok": True,
        "template": template_key,
        "fullPath": full_path,
        "createdDirs": created_dirs,
        "skippedDirs": skipped_dirs,
        "createdFiles": created_files,
        "skippedFiles": skipped_files,
    }
