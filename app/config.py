import os
from pathlib import Path


class Config:
    BASE_DIR = Path(__file__).resolve().parent.parent

    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key")
    JWT_SECRET_KEY = os.getenv("JWT_SECRET_KEY", SECRET_KEY)

    DATABASE_BACKEND = os.getenv("DATABASE_BACKEND", "sqlite").lower()

    SQLITE_DATABASE_PATH = Path(
        os.getenv(
            "SQLITE_DATABASE_PATH",
            str(BASE_DIR / "instance" / "steeltech.db"),
        )
    )

    MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
    MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3306"))
    MYSQL_USER = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
    MYSQL_DATABASE = os.getenv("MYSQL_DATABASE", "itss_steeltech")

    if DATABASE_BACKEND == "mysql":
        SQLALCHEMY_DATABASE_URI = (
            f"mysql+pymysql://{MYSQL_USER}:{MYSQL_PASSWORD}"
            f"@{MYSQL_HOST}:{MYSQL_PORT}/{MYSQL_DATABASE}?charset=utf8mb4"
        )
    else:
        SQLITE_DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
        SQLALCHEMY_DATABASE_URI = (
            "sqlite:///" + SQLITE_DATABASE_PATH.as_posix()
        )

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    CORS_ORIGINS = [
        origin.strip()
        for origin in os.getenv(
            "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
        ).split(",")
        if origin.strip()
    ]

    DEFAULT_LOGIN_PASSWORD = os.getenv("DEFAULT_LOGIN_PASSWORD", "123456")
