from __future__ import annotations

import csv
import io
import re
from datetime import datetime

from steeltech_db.extensions import db
from steeltech_db.models import Personnel

DEFAULT_WORKSHOP = "钢结构技术科"
WORKSHOP_DEV = "开发人员"
TEAM_WORKSHOP_MAP = {
    "设计组": DEFAULT_WORKSHOP,
    "细化组": DEFAULT_WORKSHOP,
    "开发组": WORKSHOP_DEV,
}


def resolve_workshop(team: str = "", workshop: str = "") -> str:
    """按班组解析科室；已知班组优先映射，否则沿用传入值或默认钢结构技术科。"""
    team_text = (team or "").strip()
    mapped = TEAM_WORKSHOP_MAP.get(team_text)
    if mapped:
        return mapped
    text = (workshop or "").strip()
    return text or DEFAULT_WORKSHOP


STATUS_LABEL_TO_CODE = {
    "在职": "active",
    "离职": "inactive",
    "休假": "leave",
    "active": "active",
    "inactive": "inactive",
    "leave": "leave",
}

STATUS_CODE_TO_LABEL = {
    "active": "在职",
    "inactive": "离职",
    "leave": "休假",
}

# CSV 表头（中文）→ payload 字段
CSV_COLUMNS: list[tuple[str, str]] = [
    ("姓名", "name"),
    ("工号", "employeeNo"),
    ("班组", "team"),
    ("车间/科室", "workshop"),
    ("国籍", "nationality"),
    ("状态", "status"),
    ("岗位", "position"),
    ("性别", "gender"),
    ("出生日期", "birthDate"),
    ("年龄", "age"),
    ("民族", "ethnicity"),
    ("籍贯", "nativePlace"),
    ("家庭住址", "homeAddress"),
    ("宿舍号", "dormitoryNo"),
    ("身份证号", "idCardNo"),
    ("护照号", "passportNo"),
    ("护照有效期", "passportExpiry"),
    ("学历", "education"),
    ("毕业院校", "graduationSchool"),
    ("所学专业", "major"),
    ("印尼号码", "indonesiaPhone"),
    ("国内号码", "domesticPhone"),
]

CSV_HEADERS = [header for header, _ in CSV_COLUMNS]


def list_personnel(*, keyword: str = "", status: str = "") -> list[dict]:
    query = Personnel.query
    status = (status or "").strip()
    if status:
        query = query.filter(Personnel.status == status)
    rows = query.order_by(Personnel.team, Personnel.name).all()
    keyword = keyword.strip().lower()
    result: list[dict] = []

    for row in rows:
        item = row.to_dict()
        if keyword:
            searchable = " ".join(
                [
                    item["id"],
                    item["name"],
                    item["employeeNo"],
                    item["nationality"],
                    item["team"],
                    item["position"],
                    item["domesticPhone"],
                ]
            ).lower()
            if keyword not in searchable:
                continue
        result.append(item)
    return result


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def generate_personnel_id() -> str:
    max_number = 0
    rows = Personnel.query.filter(Personnel.id.like("PER%")).all()
    for row in rows:
        match = re.fullmatch(r"PER(\d+)", row.id or "")
        if match:
            max_number = max(max_number, int(match.group(1)))
    # 包含当前 session 中尚未 flush 的新建对象，避免批量导入时 ID 冲突
    for obj in db.session.new:
        if isinstance(obj, Personnel):
            match = re.fullmatch(r"PER(\d+)", obj.id or "")
            if match:
                max_number = max(max_number, int(match.group(1)))
    return f"PER{max_number + 1:03d}"


def _normalize_status(value: str) -> str | None:
    text = (value or "").strip()
    if not text:
        return None
    return STATUS_LABEL_TO_CODE.get(text) or STATUS_LABEL_TO_CODE.get(text.lower())


def _validate_payload(payload: dict) -> str | None:
    if not (payload.get("name") or "").strip():
        return "姓名不能为空"
    if not (payload.get("employeeNo") or "").strip():
        return "工号不能为空"
    if not (payload.get("nationality") or "").strip():
        return "国籍不能为空"
    if not (payload.get("status") or "").strip():
        return "状态不能为空"
    status = _normalize_status(str(payload.get("status") or ""))
    if status is None:
        return "状态须为：在职 / 离职 / 休假"
    return None


def _apply_payload(row: Personnel, payload: dict) -> None:
    row.name = payload["name"].strip()
    row.employee_no = payload["employeeNo"].strip()
    row.id_card_no = payload.get("idCardNo") or ""
    row.passport_no = payload.get("passportNo") or ""
    row.passport_expiry = payload.get("passportExpiry") or ""
    row.position = payload.get("position") or ""
    row.nationality = payload["nationality"].strip()
    row.team = (payload.get("team") or "").strip()
    row.workshop = resolve_workshop(row.team, payload.get("workshop") or "")
    row.birth_date = payload.get("birthDate") or ""
    try:
        row.age = int(payload.get("age") or 0)
    except (TypeError, ValueError):
        row.age = 0
    row.gender = payload.get("gender") or ""
    row.ethnicity = payload.get("ethnicity") or ""
    row.native_place = payload.get("nativePlace") or ""
    row.education = payload.get("education") or ""
    row.home_address = payload.get("homeAddress") or ""
    row.graduation_school = payload.get("graduationSchool") or ""
    row.major = payload.get("major") or ""
    row.indonesia_phone = payload.get("indonesiaPhone") or ""
    row.domestic_phone = payload.get("domesticPhone") or ""
    row.dormitory_no = payload.get("dormitoryNo") or ""
    row.status = _normalize_status(str(payload.get("status") or "")) or "active"
    row.updated_at = _now()


def create_personnel(payload: dict) -> tuple[dict | None, str | None, int]:
    error = _validate_payload(payload)
    if error:
        return None, error, 400

    employee_no = payload["employeeNo"].strip()
    if Personnel.query.filter_by(employee_no=employee_no).first():
        return None, f"工号 {employee_no} 已存在", 409

    personnel_id = (payload.get("id") or "").strip() or generate_personnel_id()
    if Personnel.query.get(personnel_id):
        return None, f"人员 {personnel_id} 已存在", 409

    now = _now()
    row = Personnel(id=personnel_id, created_at=now, updated_at=now)
    _apply_payload(row, payload)
    db.session.add(row)
    db.session.commit()
    return row.to_dict(), None, 201


def update_personnel(personnel_id: str, payload: dict) -> tuple[dict | None, str | None, int]:
    row = Personnel.query.get(personnel_id)
    if row is None:
        return None, "人员不存在", 404

    error = _validate_payload(payload)
    if error:
        return None, error, 400

    employee_no = payload["employeeNo"].strip()
    existing = Personnel.query.filter_by(employee_no=employee_no).first()
    if existing is not None and existing.id != personnel_id:
        return None, f"工号 {employee_no} 已被其他人员使用", 409

    _apply_payload(row, payload)
    db.session.commit()
    return row.to_dict(), None, 200


def delete_personnel(personnel_id: str) -> tuple[dict | None, str | None, int]:
    row = Personnel.query.get(personnel_id)
    if row is None:
        return None, "人员不存在", 404
    db.session.delete(row)
    db.session.commit()
    return {"id": personnel_id}, None, 200


def export_personnel_csv_template() -> bytes:
    """导出带表头与示例行的 CSV 模板，供填写后导入。"""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(CSV_HEADERS)
    writer.writerow(
        [
            "张三",
            "42605001",
            "设计组",
            DEFAULT_WORKSHOP,
            "中国",
            "在职",
            "设计工程师",
            "男",
            "1995-01-15",
            "30",
            "汉族",
            "重庆市",
            "重庆市渝北区示例路 1 号",
            "B3_603",
            "",
            "",
            "",
            "本科",
            "重庆大学",
            "土木工程",
            "",
            "13800001001",
        ]
    )
    writer.writerow(
        [
            "李四",
            "42605002",
            "开发组",
            WORKSHOP_DEV,
            "中国",
            "在职",
            "开发工程师",
            "男",
            "1996-03-20",
            "29",
            "汉族",
            "重庆市",
            "重庆市渝北区示例路 2 号",
            "N1_201",
            "",
            "",
            "",
            "本科",
            "重庆大学",
            "软件工程",
            "",
            "13800001002",
        ]
    )
    # Excel 友好：UTF-8 BOM
    return ("\ufeff" + buffer.getvalue()).encode("utf-8")


def _row_to_payload(row: dict[str, str]) -> dict:
    payload: dict = {}
    for header, field in CSV_COLUMNS:
        payload[field] = (row.get(header) or "").strip()
    return payload


def import_personnel_csv(file_bytes: bytes) -> tuple[dict | None, str | None, int]:
    if not file_bytes:
        return None, "文件内容为空", 400

    text: str
    for encoding in ("utf-8-sig", "utf-8", "gbk", "gb2312"):
        try:
            text = file_bytes.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        return None, "无法识别文件编码，请使用 UTF-8 或 GBK", 400

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        return None, "CSV 缺少表头", 400

    missing = [header for header in ("姓名", "工号", "国籍", "状态") if header not in reader.fieldnames]
    if missing:
        return None, f"CSV 缺少必填列：{'、'.join(missing)}", 400

    created = 0
    updated = 0
    errors: list[str] = []

    for index, raw_row in enumerate(reader, start=2):
        if not any((value or "").strip() for value in raw_row.values()):
            continue

        payload = _row_to_payload({k: (v or "") for k, v in raw_row.items()})
        error = _validate_payload(payload)
        if error:
            errors.append(f"第 {index} 行：{error}")
            continue

        employee_no = payload["employeeNo"].strip()
        row = Personnel.query.filter_by(employee_no=employee_no).first()
        if row is None:
            now = _now()
            row = Personnel(id=generate_personnel_id(), created_at=now, updated_at=now)
            _apply_payload(row, payload)
            db.session.add(row)
            created += 1
        else:
            _apply_payload(row, payload)
            updated += 1

    if errors and created == 0 and updated == 0:
        db.session.rollback()
        return None, "；".join(errors[:5]), 400

    db.session.commit()
    message_parts = [f"成功导入 {created + updated} 条"]
    if created:
        message_parts.append(f"新建 {created}")
    if updated:
        message_parts.append(f"更新 {updated}")
    if errors:
        message_parts.append(f"跳过 {len(errors)} 条（{errors[0]}）")

    return {
        "created": created,
        "updated": updated,
        "skipped": len(errors),
        "errors": errors[:20],
        "message": "，".join(message_parts),
        "items": list_personnel(),
    }, None, 200
