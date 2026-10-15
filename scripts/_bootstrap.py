"""脚本公共引导：加载环境变量、后端路径与 Flask 应用上下文。"""

from __future__ import annotations

import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

BACKEND_ROOT = Path(__file__).resolve().parent.parent


def setup_backend_path() -> Path:
    root = str(BACKEND_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)
    return BACKEND_ROOT


def load_env() -> None:
    from dotenv import load_dotenv

    load_dotenv()
    load_dotenv(BACKEND_ROOT / ".env")


def create_app():
    setup_backend_path()
    load_env()
    from app import create_app as _create_app

    return _create_app()


@contextmanager
def app_context() -> Iterator:
    app = create_app()
    with app.app_context():
        yield app
