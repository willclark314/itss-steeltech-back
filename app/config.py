import os
from pathlib import Path

from steeltech_db.config import BaseConfig


class Config(BaseConfig):
    """后端应用配置 —— 继承数据库基础配置，添加应用特定设置。

    SQLite 数据库文件默认位于 itss-steeltech-db/datas/steeltech.db，
    可通过 SQLITE_DATABASE_PATH 环境变量覆盖。
    """

    BASE_DIR = Path(__file__).resolve().parent.parent

    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", SECRET_KEY)

    CORS_ORIGINS = [
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
        ).split(",")
        if origin.strip()
    ]

    DEFAULT_LOGIN_PASSWORD = os.getenv("DEFAULT_LOGIN_PASSWORD", "123456")
    CONTACT_PDF_STORAGE_ROOT = Path(
        os.getenv(
            "CONTACT_PDF_STORAGE_ROOT",
            str(BASE_DIR / "datas" / "files" / "contact-pdfs"),
        )
    )
