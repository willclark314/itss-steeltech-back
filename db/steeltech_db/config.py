from pathlib import Path

from dotenv import load_dotenv

from steeltech_db.database_url import resolve_database_settings

# db/steeltech_db/config.py -> 后端根目录 itss-steeltech-back/
_BACKEND_ROOT = Path(__file__).resolve().parents[2]


def load_backend_dotenv() -> None:
    """加载后端根目录与当前工作目录的 .env。可重复调用。"""
    load_dotenv(_BACKEND_ROOT / ".env")
    load_dotenv()


# 在解析数据库配置之前加载环境变量，避免 import 早于 create_app 内 load_dotenv
load_backend_dotenv()


class BaseConfig:
    """数据库相关配置 —— 后端 Config 继承此类并添加应用特定设置。"""

    _PACKAGE_DIR = Path(__file__).resolve().parent.parent
    _DEFAULT_SQLITE_PATH = (_PACKAGE_DIR / "datas" / "steeltech.db").resolve()

    SQLALCHEMY_TRACK_MODIFICATIONS = False

    DATABASE_BACKEND: str
    SQLALCHEMY_DATABASE_URI: str
    SQLITE_DATABASE_PATH: Path

    @classmethod
    def refresh_from_env(cls, env=None) -> dict:
        """按当前环境变量重新解析并写回类属性。应在 load_dotenv 之后调用。"""
        settings = resolve_database_settings(
            env,
            default_sqlite_path=cls._DEFAULT_SQLITE_PATH,
        )
        cls.DATABASE_BACKEND = settings["DATABASE_BACKEND"]  # type: ignore[assignment]
        cls.SQLALCHEMY_DATABASE_URI = settings["SQLALCHEMY_DATABASE_URI"]  # type: ignore[assignment]
        cls.SQLITE_DATABASE_PATH = settings["SQLITE_DATABASE_PATH"]  # type: ignore[assignment]
        return settings


BaseConfig.refresh_from_env()
