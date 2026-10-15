from __future__ import annotations

import base64
import io
import json
import mimetypes
import uuid
from datetime import datetime
from pathlib import Path
from urllib.parse import quote

from app.config import Config
from steeltech_db.extensions import db
from steeltech_db.models.monthly_training import (
    MonthlyTraining,
    MonthlyTrainingMaterial,
    MonthlyTrainingPhoto,
)

FILE_ROOT = Path(Config.MONTHLY_TRAINING_FILE_ROOT)
MAX_MATERIALS = 10
MAX_PHOTOS = 5

CATEGORY_TAGS = ["制度类", "管理类", "质量类", "安全类", "技能类"]

MATERIAL_TYPE_LABELS: dict[str, str] = {
    "training_ppt": "培训课件",
    "policy_doc": "制度原文",
    "signin_sheet": "签到表",
    "training_record": "培训记录",
}


def _now_local() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def _generate_id() -> str:
    return uuid.uuid4().hex[:16]


def _training_to_dict(training: MonthlyTraining) -> dict:
    materials = (
        MonthlyTrainingMaterial.query
        .filter_by(training_id=training.id)
        .order_by(MonthlyTrainingMaterial.sort_order)
        .all()
    )
    photos = (
        MonthlyTrainingPhoto.query
        .filter_by(training_id=training.id)
        .order_by(MonthlyTrainingPhoto.sort_order)
        .all()
    )
    return {
        "id": training.id,
        "trainingYear": training.training_year,
        "trainingMonth": training.training_month,
        "itemSeq": training.item_seq,
        "categoryTag": training.category_tag,
        "title": training.title,
        "trainer": training.trainer,
        "archiveNo": training.archive_no or "",
        "trainingDate": training.training_date or "",
        "primaryPdf": _primary_pdf_to_dict(training),
        "materials": [_material_to_dict(m) for m in materials],
        "photos": [_photo_to_dict(p) for p in photos],
        "createdAt": training.created_at,
        "updatedAt": training.updated_at,
    }


def _primary_pdf_to_dict(training: MonthlyTraining) -> dict | None:
    if not training.content_file_path:
        return None
    return {
        "fileName": training.content_file_name or "",
        "filePath": training.content_file_path,
        "fileSize": training.content_file_size or 0,
        "mimeType": training.content_mime_type or "application/pdf",
        "url": f"/api/monthly-training-files/{training.content_file_path}",
    }


def _material_to_dict(material: MonthlyTrainingMaterial) -> dict:
    return {
        "id": material.id,
        "trainingId": material.training_id,
        "fileName": material.file_name,
        "filePath": material.file_path,
        "fileSize": material.file_size,
        "mimeType": material.mime_type,
        "materialType": material.material_type,
        "sortOrder": material.sort_order,
        "url": f"/api/monthly-training-files/{material.file_path}",
        "createdAt": material.created_at,
    }


def _photo_to_dict(photo: MonthlyTrainingPhoto) -> dict:
    return {
        "id": photo.id,
        "trainingId": photo.training_id,
        "fileName": photo.file_name,
        "filePath": photo.file_path,
        "fileSize": photo.file_size,
        "mimeType": photo.mime_type,
        "sortOrder": photo.sort_order,
        "url": f"/api/monthly-training-files/{photo.file_path}",
        "createdAt": photo.created_at,
    }


# ── CRUD ────────────────────────────────────────────────────────────────────


def list_trainings(year: str = "", month: str = "") -> dict:
    query = MonthlyTraining.query
    if year:
        query = query.filter(MonthlyTraining.training_year == year)
    if month:
        query = query.filter(MonthlyTraining.training_month == month)
    query = query.order_by(
        MonthlyTraining.training_year.desc(),
        MonthlyTraining.training_month.desc(),
        MonthlyTraining.item_seq.asc(),
    )

    trainings = query.all()
    return {
        "list": [_training_to_dict(t) for t in trainings],
        "total": len(trainings),
    }


def get_training(training_id: str) -> dict | None:
    training = MonthlyTraining.query.get(training_id)
    if not training:
        return None
    return _training_to_dict(training)


def _default_archive_no(year: str, month: str) -> str:
    year = (year or "").strip()
    month = (month or "").strip().zfill(2) if (month or "").strip() else ""
    if not year or not month:
        return ""
    return f"DTP-GGJSK{year}-{month}A"


def create_training(payload: dict) -> dict:
    year = str(payload.get("trainingYear", "")).strip()
    month = str(payload.get("trainingMonth", "")).strip()
    archive_no = str(payload.get("archiveNo", "")).strip() or _default_archive_no(year, month)
    training = MonthlyTraining(
        id=_generate_id(),
        training_year=year,
        training_month=month,
        item_seq=int(payload.get("itemSeq", 1)),
        category_tag=str(payload.get("categoryTag", "")).strip(),
        title=str(payload.get("title", "")).strip(),
        trainer=str(payload.get("trainer", "")).strip(),
        archive_no=archive_no,
        training_date=str(payload.get("trainingDate", "")).strip(),
        created_at=_now_local(),
    )
    db.session.add(training)
    db.session.commit()
    return _training_to_dict(training)


def update_training(training_id: str, payload: dict) -> dict | None:
    training = MonthlyTraining.query.get(training_id)
    if not training:
        return None

    if "trainingYear" in payload:
        training.training_year = str(payload["trainingYear"]).strip()
    if "trainingMonth" in payload:
        training.training_month = str(payload["trainingMonth"]).strip()
    if "itemSeq" in payload:
        training.item_seq = int(payload["itemSeq"])
    if "categoryTag" in payload:
        training.category_tag = str(payload["categoryTag"]).strip()
    if "title" in payload:
        training.title = str(payload["title"]).strip()
    if "trainer" in payload:
        training.trainer = str(payload["trainer"]).strip()
    if "archiveNo" in payload:
        training.archive_no = str(payload["archiveNo"]).strip()
    if "trainingDate" in payload:
        training.training_date = str(payload["trainingDate"]).strip()

    if not (training.archive_no or "").strip():
        training.archive_no = _default_archive_no(training.training_year, training.training_month)

    training.updated_at = _now_local()
    db.session.commit()
    return _training_to_dict(training)


def delete_training(training_id: str) -> bool:
    training = MonthlyTraining.query.get(training_id)
    if not training:
        return False

    if training.content_file_path:
        _delete_file(training.content_file_path)

    materials = MonthlyTrainingMaterial.query.filter_by(training_id=training_id).all()
    for mat in materials:
        _delete_file(mat.file_path)
        db.session.delete(mat)

    photos = MonthlyTrainingPhoto.query.filter_by(training_id=training_id).all()
    for photo in photos:
        _delete_file(photo.file_path)
        db.session.delete(photo)

    db.session.delete(training)
    db.session.commit()
    return True


# ── File helpers ────────────────────────────────────────────────────────────


def _delete_file(relative_path: str) -> None:
    try:
        file_path = FILE_ROOT / relative_path
        if file_path.exists():
            file_path.unlink()
    except Exception:
        pass


def _guess_ext(file_name: str, mime_type: str) -> str:
    if mime_type:
        ext = mimetypes.guess_extension(mime_type)
        if ext:
            return ext
    return Path(file_name).suffix or ".pdf"


def _save_file(training_id: str, file_info: dict) -> tuple[str, str, int]:
    """Save a base64-encoded file. Returns (relative_path, absolute bytes_size)."""
    file_name = str(file_info.get("fileName", "file.pdf"))
    content_b64 = str(file_info.get("content", ""))
    mime_type = str(file_info.get("mimeType", "application/pdf"))

    try:
        raw_bytes = base64.b64decode(content_b64)
    except Exception:
        raise ValueError("文件内容无效")

    ext = _guess_ext(file_name, mime_type)
    stored_name = f"{uuid.uuid4().hex[:8]}{ext}"
    relative_path = f"{training_id}/{stored_name}"
    full_path = FILE_ROOT / relative_path
    full_path.parent.mkdir(parents=True, exist_ok=True)
    full_path.write_bytes(raw_bytes)

    return relative_path, file_name, len(raw_bytes)


# ── Primary PDF (正文) ───────────────────────────────────────────────────────


def _is_pdf_file(file_info: dict) -> bool:
    file_name = str(file_info.get("fileName", "")).lower()
    mime_type = str(file_info.get("mimeType", "")).lower()
    return file_name.endswith(".pdf") or mime_type in (
        "application/pdf",
        "application/x-pdf",
    )


def save_training_primary_pdf(training_id: str, file_info: dict) -> dict:
    training = MonthlyTraining.query.get(training_id)
    if not training:
        raise ValueError("培训记录不存在")
    if not _is_pdf_file(file_info):
        raise ValueError("正文仅支持 PDF 文件")

    if training.content_file_path:
        _delete_file(training.content_file_path)

    relative_path, file_name, file_size = _save_file(training_id, file_info)
    training.content_file_name = file_name
    training.content_file_path = relative_path
    training.content_file_size = file_size
    training.content_mime_type = str(file_info.get("mimeType") or "application/pdf")
    training.updated_at = _now_local()
    db.session.commit()
    return _training_to_dict(training)


def delete_training_primary_pdf(training_id: str) -> bool:
    training = MonthlyTraining.query.get(training_id)
    if not training:
        return False
    if not training.content_file_path:
        return True

    _delete_file(training.content_file_path)
    training.content_file_name = None
    training.content_file_path = None
    training.content_file_size = None
    training.content_mime_type = None
    training.updated_at = _now_local()
    db.session.commit()
    return True


# ── Material management ─────────────────────────────────────────────────────


def save_training_material(
    training_id: str, file_info: dict, material_type: str = ""
) -> dict:
    training = MonthlyTraining.query.get(training_id)
    if not training:
        raise ValueError("培训记录不存在")

    existing_count = MonthlyTrainingMaterial.query.filter_by(
        training_id=training_id
    ).count()
    if existing_count >= MAX_MATERIALS:
        raise ValueError(f"每条培训记录最多上传 {MAX_MATERIALS} 个文件")

    current_max = (
        db.session.query(db.func.max(MonthlyTrainingMaterial.sort_order))
        .filter_by(training_id=training_id)
        .scalar()
    ) or 0

    relative_path, file_name, file_size = _save_file(training_id, file_info)

    material = MonthlyTrainingMaterial(
        id=_generate_id(),
        training_id=training_id,
        file_name=file_name,
        file_path=relative_path,
        file_size=file_size,
        mime_type=str(file_info.get("mimeType", "application/pdf")),
        material_type=material_type,
        sort_order=current_max + 1,
        created_at=_now_local(),
    )
    db.session.add(material)
    db.session.commit()
    return _material_to_dict(material)


def delete_training_material(training_id: str, material_id: str) -> bool:
    material = MonthlyTrainingMaterial.query.filter_by(
        id=material_id, training_id=training_id
    ).first()
    if not material:
        return False
    _delete_file(material.file_path)
    db.session.delete(material)
    db.session.commit()
    return True


# ── Photo management ────────────────────────────────────────────────────────


def save_training_photos(training_id: str, files: list[dict]) -> list[dict]:
    training = MonthlyTraining.query.get(training_id)
    if not training:
        raise ValueError("培训记录不存在")

    existing_count = MonthlyTrainingPhoto.query.filter_by(
        training_id=training_id
    ).count()
    if existing_count + len(files) > MAX_PHOTOS:
        raise ValueError(f"每条培训记录最多上传 {MAX_PHOTOS} 张照片")

    current_max = (
        db.session.query(db.func.max(MonthlyTrainingPhoto.sort_order))
        .filter_by(training_id=training_id)
        .scalar()
    ) or 0

    saved = []
    for index, file_info in enumerate(files):
        try:
            relative_path, file_name, file_size = _save_file(training_id, file_info)
        except ValueError:
            continue

        photo = MonthlyTrainingPhoto(
            id=_generate_id(),
            training_id=training_id,
            file_name=file_name,
            file_path=relative_path,
            file_size=file_size,
            mime_type=str(file_info.get("mimeType", "image/png")),
            sort_order=current_max + index + 1,
            created_at=_now_local(),
        )
        db.session.add(photo)
        saved.append(photo)

    db.session.commit()
    return [_photo_to_dict(p) for p in saved]


def delete_training_photo(training_id: str, photo_id: str) -> bool:
    photo = MonthlyTrainingPhoto.query.filter_by(
        id=photo_id, training_id=training_id
    ).first()
    if not photo:
        return False
    _delete_file(photo.file_path)
    db.session.delete(photo)
    db.session.commit()
    return True


# ── DOCX Export（对齐「签到表及照片页.xlsx」：照片记录表 + 签到表）────────────

_DEFAULT_TRAINING_LOCATION = "CSP办公楼208办公室"
_DEFAULT_PESERTA = "中国籍全员"
_PHOTO_LABELS = [
    ("Foto pertama", "照片一"),
    ("Foto kedua", "照片二"),
    ("Foto ketiga", "照片三"),
    ("Foto keempat", "照片四"),
    ("Foto kelima", "照片五"),
]


def export_training_docx(training_id: str) -> bytes | None:
    """导出 Word：培训照片记录表 + 培训签到表（版式对齐 Excel 模板）。"""
    training_data = get_training(training_id)
    if not training_data:
        return None

    try:
        from docx import Document
        from docx.shared import Pt, Cm
        from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
        from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ROW_HEIGHT_RULE
        from docx.oxml.ns import qn
        from docx.oxml import OxmlElement
    except ImportError:
        raise ImportError("python-docx is required for DOCX export")

    def _set_run_east_asian(run, font_name: str = "宋体"):
        run.element.rPr.rFonts.set(qn("w:eastAsia"), font_name)

    def _style_run(run, *, size: float = 10.5, bold: bool = False, font: str = "Times New Roman"):
        run.bold = bold
        run.font.size = Pt(size)
        run.font.name = font
        _set_run_east_asian(run)

    def _set_cell_text(
        cell,
        text: str,
        *,
        bold: bool = False,
        size: float = 9,
        align=WD_ALIGN_PARAGRAPH.CENTER,
        clear: bool = True,
    ):
        if clear:
            cell.text = ""
        p = cell.paragraphs[0]
        p.alignment = align
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(0)
        run = p.add_run(text)
        _style_run(run, size=size, bold=bold)
        return run

    def _set_row_height(row, height_cm: float, *, exact: bool = False):
        row.height = Cm(height_cm)
        row.height_rule = (
            WD_ROW_HEIGHT_RULE.EXACTLY if exact else WD_ROW_HEIGHT_RULE.AT_LEAST
        )

    def _set_cell_margins(cell, top=20, bottom=20, left=30, right=30):
        tc = cell._tc
        tcPr = tc.get_or_add_tcPr()
        tcMar = OxmlElement("w:tcMar")
        for name, val in (("top", top), ("left", left), ("bottom", bottom), ("right", right)):
            node = OxmlElement(f"w:{name}")
            node.set(qn("w:w"), str(val))
            node.set(qn("w:type"), "dxa")
            tcMar.append(node)
        tcPr.append(tcMar)

    def _merge(table, r1: int, c1: int, r2: int, c2: int):
        table.cell(r1, c1).merge(table.cell(r2, c2))

    def _set_col_widths(table, widths_cm: list[float]):
        for row in table.rows:
            for i, w in enumerate(widths_cm):
                row.cells[i].width = Cm(w)

    def _add_page_break():
        p = doc.add_paragraph()
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.line_spacing = 1.0
        run = p.add_run()
        run.add_break(WD_BREAK.PAGE)

    def _fit_image_cm(
        photo_path: Path,
        *,
        max_width_cm: float,
        max_height_cm: float,
    ) -> tuple[float, float]:
        """按比例缩放到单元格内，保证不撑破表格边框。"""
        width_cm = max_width_cm
        height_cm = max_height_cm
        try:
            from PIL import Image

            with Image.open(photo_path) as img:
                px_w, px_h = img.size
            if px_w > 0 and px_h > 0:
                height_cm = width_cm * (px_h / px_w)
                if height_cm > max_height_cm:
                    height_cm = max_height_cm
                    width_cm = height_cm * (px_w / px_h)
                if width_cm > max_width_cm:
                    width_cm = max_width_cm
                    height_cm = width_cm * (px_h / px_w)
                return width_cm, height_cm
        except Exception:
            pass
        # 无 PIL 时按横图安全框缩小，避免竖图撑破单元格
        return max_width_cm, min(max_height_cm, max_width_cm * 0.72)

    def _put_picture_in_cell(
        cell,
        photo_path: Path | None,
        *,
        max_width_cm: float,
        max_height_cm: float,
    ) -> float:
        """插入图片到单元格内，返回实际占用高度(cm)。"""
        cell.text = ""
        p = cell.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(0)
        p.paragraph_format.space_after = Pt(0)
        p.paragraph_format.line_spacing = 1.0
        if not (photo_path and photo_path.exists()):
            return max_height_cm
        try:
            width_cm, height_cm = _fit_image_cm(
                photo_path,
                max_width_cm=max_width_cm,
                max_height_cm=max_height_cm,
            )
            run = p.add_run()
            run.add_picture(str(photo_path), width=Cm(width_cm), height=Cm(height_cm))
            return height_cm
        except Exception:
            return max_height_cm

    title_text = training_data["title"] or ""
    trainer = training_data["trainer"] or ""
    year = training_data["trainingYear"] or ""
    month = training_data["trainingMonth"] or ""
    training_date = (training_data.get("trainingDate") or "").strip()
    archive_no = (training_data.get("archiveNo") or "").strip()
    if not archive_no:
        archive_no = _default_archive_no(year, month)

    month_int = int(month) if str(month).isdigit() else month
    if training_date and len(training_date) >= 10 and training_date[4] == "-":
        try:
            y = int(training_date[0:4])
            m = int(training_date[5:7])
            d = int(training_date[8:10])
            photo_date = f"{y}.{m}.{d}"
            waktu = f"{y}年{m}月{d}日 __点__分到__点__分"
        except Exception:
            photo_date = f"{year}.{month_int}"
            waktu = f"{year}年{month_int}月__日 __点__分到__点__分"
    else:
        photo_date = f"{year}.{month_int}"
        waktu = f"{year}年{month_int}月__日 __点__分到__点__分"

    photos = training_data.get("photos", [])[:MAX_PHOTOS]

    doc = Document()
    section = doc.sections[0]
    section.page_width = Cm(21)
    section.page_height = Cm(29.7)
    # 可用高度约 27.3cm，保证两张表各自落在单页
    section.top_margin = Cm(1.2)
    section.bottom_margin = Cm(1.2)
    section.left_margin = Cm(1.2)
    section.right_margin = Cm(1.2)

    style = doc.styles["Normal"]
    style.font.name = "Times New Roman"
    style.font.size = Pt(10.5)
    style.element.rPr.rFonts.set(qn("w:eastAsia"), "宋体")

    # ── 第 1 页：培训照片记录表（整表，对齐 Excel，固定 2 张照片）──────────
    # 标题/标签/日期约 3.2cm，两张照片区各约 11.5cm → 合计约 26.2cm
    photo_slots = 2
    photo_rows = 2 + photo_slots * 2 + 1  # 7
    photo_table = doc.add_table(rows=photo_rows, cols=1)
    photo_table.alignment = WD_TABLE_ALIGNMENT.CENTER
    photo_table.style = "Table Grid"
    photo_table.autofit = False
    photo_col_w = 18.6
    _set_col_widths(photo_table, [photo_col_w])

    _set_row_height(photo_table.rows[0], 0.7, exact=True)
    _set_cell_margins(photo_table.cell(0, 0), top=20, bottom=20, left=40, right=40)
    _set_cell_text(photo_table.cell(0, 0), "Foto pelatihan", bold=True, size=12)

    _set_row_height(photo_table.rows[1], 0.75, exact=True)
    _set_cell_margins(photo_table.cell(1, 0), top=20, bottom=20, left=40, right=40)
    _set_cell_text(photo_table.cell(1, 0), "培训照片记录表", bold=True, size=14)

    # 单元格内边距后，图片必须严格小于行高/列宽，才能留在表格边框内
    photo_row_h = 11.5
    photo_pad_cm = 0.55
    photo_max_w = photo_col_w - 1.0
    photo_max_h = photo_row_h - photo_pad_cm * 2

    for idx in range(photo_slots):
        id_label, cn_label = _PHOTO_LABELS[idx]
        label_row = 2 + idx * 2
        image_row = label_row + 1

        _set_row_height(photo_table.rows[label_row], 0.55, exact=True)
        label_cell = photo_table.cell(label_row, 0)
        _set_cell_margins(label_cell, top=10, bottom=10, left=60, right=20)
        _set_cell_text(
            label_cell,
            f"{id_label}  {cn_label}",
            bold=True,
            size=10,
            align=WD_ALIGN_PARAGRAPH.LEFT,
        )

        image_cell = photo_table.cell(image_row, 0)
        _set_cell_margins(image_cell, top=40, bottom=40, left=60, right=60)
        _set_row_height(photo_table.rows[image_row], photo_row_h, exact=True)
        photo_info = photos[idx] if idx < len(photos) else None
        photo_path = FILE_ROOT / photo_info["filePath"] if photo_info else None
        _put_picture_in_cell(
            image_cell,
            photo_path,
            max_width_cm=photo_max_w,
            max_height_cm=photo_max_h,
        )

    date_row = photo_rows - 1
    _set_row_height(photo_table.rows[date_row], 0.65, exact=True)
    date_cell = photo_table.cell(date_row, 0)
    _set_cell_margins(date_cell, top=10, bottom=10, left=40, right=80)
    _set_cell_text(
        date_cell,
        photo_date,
        bold=True,
        size=11,
        align=WD_ALIGN_PARAGRAPH.RIGHT,
    )

    _add_page_break()

    # ── 第 2 页：培训签到表（整表：标题+信息+双栏签到）─────────────────────
    # 行高合计约：0.75+0.8+1.0*3+0.95+0.95*20 ≈ 24.5cm < 27.3cm
    sign = doc.add_table(rows=26, cols=8)
    sign.alignment = WD_TABLE_ALIGNMENT.CENTER
    sign.style = "Table Grid"
    sign.autofit = False
    sign_widths = [1.0, 2.2, 3.3, 2.4, 1.0, 2.2, 3.3, 2.4]
    _set_col_widths(sign, sign_widths)

    # 标题行
    _merge(sign, 0, 0, 0, 7)
    _merge(sign, 1, 0, 1, 7)
    _set_row_height(sign.rows[0], 0.75, exact=True)
    _set_row_height(sign.rows[1], 0.8, exact=True)
    _set_cell_margins(sign.cell(0, 0), top=15, bottom=15, left=20, right=20)
    _set_cell_margins(sign.cell(1, 0), top=15, bottom=15, left=20, right=20)
    _set_cell_text(sign.cell(0, 0), "Form Pendaftaran Pelatihan", bold=True, size=12)
    _set_cell_text(sign.cell(1, 0), "培 训 签 到 表", bold=True, size=14)

    # 信息行：每组两列合并（标签 | 值 | 标签 | 值）
    info_rows = [
        (
            2,
            "Tema Pelatihan\n培训主题",
            title_text,
            "Nomer Arsip\n档案编号",
            archive_no,
        ),
        (
            3,
            "Waktu Pelatihan\n培训时间",
            waktu,
            "Tempat Pelatihan\n培训地点",
            _DEFAULT_TRAINING_LOCATION,
        ),
        (
            4,
            "Trainer\n培训讲师",
            trainer,
            "Peserta\n参加人员",
            _DEFAULT_PESERTA,
        ),
    ]
    for r, label_l, value_l, label_r, value_r in info_rows:
        _merge(sign, r, 0, r, 1)
        _merge(sign, r, 2, r, 3)
        _merge(sign, r, 4, r, 5)
        _merge(sign, r, 6, r, 7)
        _set_row_height(sign.rows[r], 1.0, exact=True)
        for c in (0, 2, 4, 6):
            _set_cell_margins(sign.cell(r, c), top=20, bottom=20, left=20, right=20)
        _set_cell_text(sign.cell(r, 0), label_l, bold=True, size=8)
        _set_cell_text(sign.cell(r, 2), value_l, bold=False, size=8.5)
        _set_cell_text(sign.cell(r, 4), label_r, bold=True, size=8)
        _set_cell_text(sign.cell(r, 6), value_r, bold=False, size=8.5)

    # 签到表头
    headers_row = [
        "No.\n序号",
        "Dept.\n部门",
        "Nama Lengkap\n姓名",
        "Waktu Hadir\n签到时间",
        "No.\n序号",
        "Dept.\n部门",
        "Nama Lengkap\n姓名",
        "Waktu Hadir\n签到时间",
    ]
    _set_row_height(sign.rows[5], 0.95, exact=True)
    for c, text in enumerate(headers_row):
        _set_cell_margins(sign.cell(5, c), top=15, bottom=15, left=10, right=10)
        _set_cell_text(sign.cell(5, c), text, bold=True, size=8)

    # 双栏序号 1-20 / 21-40
    for i in range(20):
        r = 6 + i
        _set_row_height(sign.rows[r], 0.95, exact=True)
        for c in range(8):
            _set_cell_margins(sign.cell(r, c), top=10, bottom=10, left=10, right=10)
        _set_cell_text(sign.cell(r, 0), str(i + 1), size=8.5)
        _set_cell_text(sign.cell(r, 4), str(i + 21), size=8.5)

    buffer = io.BytesIO()
    doc.save(buffer)
    buffer.seek(0)
    return buffer.getvalue()
