"""验证同一套 SQLAlchemy 模型在 SQLite 与 MySQL 上均可建表、读写。"""

import os

import pymysql
import pytest
from dotenv import load_dotenv
from sqlalchemy.pool import StaticPool

from app import create_app
from app.config import Config
from steeltech_db.extensions import db
from steeltech_db.models import AccountPassword

load_dotenv()


class SqliteTestConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret-key-for-pytest-only-32b"
    JWT_SECRET_KEY = "test-secret-key-for-pytest-only-32b"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "connect_args": {"check_same_thread": False},
        "poolclass": StaticPool,
    }
    CORS_ORIGINS = ["http://localhost:5173"]


def _mysql_test_database_uri():
    host = os.getenv("MYSQL_HOST", "127.0.0.1")
    port = int(os.getenv("MYSQL_PORT", "3306"))
    user = os.getenv("MYSQL_USER", "root")
    password = os.getenv("MYSQL_PASSWORD", "")
    database = os.getenv("MYSQL_TEST_DATABASE", "itss_steeltech_test")
    return (
        f"mysql+pymysql://{user}:{password}@{host}:{port}/{database}?charset=utf8mb4"
    )


class MySQLTestConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret-key-for-pytest-only-32b"
    JWT_SECRET_KEY = "test-secret-key-for-pytest-only-32b"
    SQLALCHEMY_DATABASE_URI = _mysql_test_database_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    CORS_ORIGINS = ["http://localhost:5173"]


def _ensure_mysql_test_database():
    host = os.getenv("MYSQL_HOST", "127.0.0.1")
    port = int(os.getenv("MYSQL_PORT", "3306"))
    user = os.getenv("MYSQL_USER", "root")
    password = os.getenv("MYSQL_PASSWORD", "")
    database = os.getenv("MYSQL_TEST_DATABASE", "itss_steeltech_test")

    conn = pymysql.connect(
        host=host,
        port=port,
        user=user,
        password=password,
        charset="utf8mb4",
    )
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{database}` "
                "DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        conn.commit()
    finally:
        conn.close()


def _mysql_available():
    try:
        _ensure_mysql_test_database()
        app = create_app(MySQLTestConfig)
        with app.app_context():
            db.engine.connect().close()
        return True
    except Exception:
        return False


BACKEND_CONFIGS: list[tuple[str, type[Config]]] = [("sqlite", SqliteTestConfig)]
if _mysql_available():
    BACKEND_CONFIGS.append(("mysql", MySQLTestConfig))


@pytest.fixture(params=BACKEND_CONFIGS, ids=[name for name, _ in BACKEND_CONFIGS])
def backend_app(request):
    config_class = request.param[1]
    app = create_app(config_class)
    with app.app_context():
        db.drop_all()
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


def test_create_all(backend_app):
    with backend_app.app_context():
        tables = db.inspect(db.engine).get_table_names()
        assert "personnel" in tables
        assert "account_passwords" in tables
        assert "users" not in tables


def test_account_password_crud(backend_app):
    with backend_app.app_context():
        row = AccountPassword(account="42601001", password="secret123")
        db.session.add(row)
        db.session.commit()

        loaded = AccountPassword.query.filter_by(account="42601001").first()
        assert loaded is not None
        assert loaded.password == "secret123"


def test_login_api_on_backend(backend_app):
    client = backend_app.test_client()
    resp = client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "123456"},
    )
    assert resp.status_code == 200
    assert "token" in resp.get_json()
