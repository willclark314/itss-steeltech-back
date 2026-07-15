import os
from datetime import timedelta
from pathlib import Path

from steeltech_db.config import BaseConfig


class Config(BaseConfig):
    """后端应用配置 —— 继承数据库基础配置，添加应用特定设置。

    数据库连接优先读取 DATABASE_URL（或 SQLALCHEMY_DATABASE_URI）；
    未设置时使用 DATABASE_BACKEND + SQLITE_DATABASE_PATH / MYSQL_* 分散变量。
    """

    BASE_DIR = Path(__file__).resolve().parent.parent

    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", SECRET_KEY)
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(
        hours=int(os.getenv("JWT_ACCESS_TOKEN_HOURS", "8"))
    )

    CORS_ORIGINS = [
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
        ).split(",")
        if origin.strip()
    ]

    DEFAULT_LOGIN_PASSWORD = os.getenv("DEFAULT_LOGIN_PASSWORD", "123456")

    _contact_pdf_storage_root = Path(
        os.getenv(
            "CONTACT_PDF_STORAGE_ROOT",
            str(BASE_DIR / "datas" / "files" / "contact-pdfs"),
        )
    )
    if not _contact_pdf_storage_root.is_absolute():
        _contact_pdf_storage_root = (BASE_DIR / _contact_pdf_storage_root).resolve()
    CONTACT_PDF_STORAGE_ROOT = _contact_pdf_storage_root

    _contact_attachment_storage_root = Path(
        os.getenv(
            "CONTACT_ATTACHMENT_STORAGE_ROOT",
            str(BASE_DIR / "datas" / "files" / "contact-attachments"),
        )
    )
    if not _contact_attachment_storage_root.is_absolute():
        _contact_attachment_storage_root = (
            BASE_DIR / _contact_attachment_storage_root
        ).resolve()
    CONTACT_ATTACHMENT_STORAGE_ROOT = _contact_attachment_storage_root

    _weekly_meeting_image_root = Path(
        os.getenv(
            "WEEKLY_MEETING_IMAGE_ROOT",
            str(BASE_DIR / "datas" / "files" / "weekly-meeting-images"),
        )
    )
    if not _weekly_meeting_image_root.is_absolute():
        _weekly_meeting_image_root = (
            BASE_DIR / _weekly_meeting_image_root
        ).resolve()
    WEEKLY_MEETING_IMAGE_ROOT = _weekly_meeting_image_root

    _weekly_meeting_scan_root = Path(
        os.getenv(
            "WEEKLY_MEETING_SCAN_ROOT",
            str(BASE_DIR / "datas" / "files" / "weekly-meeting-scans"),
        )
    )
    if not _weekly_meeting_scan_root.is_absolute():
        _weekly_meeting_scan_root = (
            BASE_DIR / _weekly_meeting_scan_root
        ).resolve()
    WEEKLY_MEETING_SCAN_ROOT = _weekly_meeting_scan_root

    _director_interview_image_root = Path(
        os.getenv(
            "DIRECTOR_INTERVIEW_IMAGE_ROOT",
            str(BASE_DIR / "datas" / "files" / "director-interview-images"),
        )
    )
    if not _director_interview_image_root.is_absolute():
        _director_interview_image_root = (
            BASE_DIR / _director_interview_image_root
        ).resolve()
    DIRECTOR_INTERVIEW_IMAGE_ROOT = _director_interview_image_root
