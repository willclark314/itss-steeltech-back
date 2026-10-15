import os
from datetime import timedelta
from pathlib import Path

from steeltech_db.config import BaseConfig, load_backend_dotenv

# BaseConfig 导入时已加载 .env；此处再调一次保证直接 import Config 时也安全
load_backend_dotenv()


def _resolve_storage_path(env_key: str, default: Path, base_dir: Path) -> Path:
    raw = Path(os.getenv(env_key, str(default)))
    if not raw.is_absolute():
        return (base_dir / raw).resolve()
    return raw.resolve()


class Config(BaseConfig):
    """后端应用配置 —— 继承数据库基础配置，添加应用特定设置。

    数据库连接优先读取 DATABASE_URL（或 SQLALCHEMY_DATABASE_URI）；
    未设置时默认 SQLite。
    """

    BASE_DIR = Path(__file__).resolve().parent.parent

    SECRET_KEY: str
    JWT_SECRET_KEY: str
    JWT_ACCESS_TOKEN_EXPIRES: timedelta
    CORS_ORIGINS: list[str]
    DEFAULT_LOGIN_PASSWORD: str
    CONTACT_PDF_STORAGE_ROOT: Path
    CONTACT_ATTACHMENT_STORAGE_ROOT: Path
    WEEKLY_MEETING_IMAGE_ROOT: Path
    WEEKLY_MEETING_SCAN_ROOT: Path
    DIRECTOR_INTERVIEW_IMAGE_ROOT: Path
    CHANGE_ORDER_PDF_STORAGE_ROOT: Path
    MONTHLY_TRAINING_FILE_ROOT: Path

    @classmethod
    def refresh_from_env(cls, env=None) -> dict:
        """在 load_dotenv 之后调用：刷新数据库与应用侧环境配置。"""
        settings = super().refresh_from_env(env)

        cls.SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
        cls.JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", cls.SECRET_KEY)
        cls.JWT_ACCESS_TOKEN_EXPIRES = timedelta(
            hours=int(os.getenv("JWT_ACCESS_TOKEN_HOURS", "8"))
        )
        cls.CORS_ORIGINS = [
            origin.strip()
            for origin in os.getenv(
                "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
            ).split(",")
            if origin.strip()
        ]
        cls.DEFAULT_LOGIN_PASSWORD = os.getenv("DEFAULT_LOGIN_PASSWORD", "123456")

        base = cls.BASE_DIR
        cls.CONTACT_PDF_STORAGE_ROOT = _resolve_storage_path(
            "CONTACT_PDF_STORAGE_ROOT",
            base / "datas" / "files" / "contact-pdfs",
            base,
        )
        cls.CONTACT_ATTACHMENT_STORAGE_ROOT = _resolve_storage_path(
            "CONTACT_ATTACHMENT_STORAGE_ROOT",
            base / "datas" / "files" / "contact-attachments",
            base,
        )
        cls.WEEKLY_MEETING_IMAGE_ROOT = _resolve_storage_path(
            "WEEKLY_MEETING_IMAGE_ROOT",
            base / "datas" / "files" / "weekly-meeting-images",
            base,
        )
        cls.WEEKLY_MEETING_SCAN_ROOT = _resolve_storage_path(
            "WEEKLY_MEETING_SCAN_ROOT",
            base / "datas" / "files" / "weekly-meeting-scans",
            base,
        )
        cls.DIRECTOR_INTERVIEW_IMAGE_ROOT = _resolve_storage_path(
            "DIRECTOR_INTERVIEW_IMAGE_ROOT",
            base / "datas" / "files" / "director-interview-images",
            base,
        )
        cls.CHANGE_ORDER_PDF_STORAGE_ROOT = _resolve_storage_path(
            "CHANGE_ORDER_PDF_STORAGE_ROOT",
            base / "datas" / "files" / "change-order-pdfs",
            base,
        )
        cls.MONTHLY_TRAINING_FILE_ROOT = _resolve_storage_path(
            "MONTHLY_TRAINING_FILE_ROOT",
            base / "datas" / "files" / "monthly-training-files",
            base,
        )
        return settings


Config.refresh_from_env()
