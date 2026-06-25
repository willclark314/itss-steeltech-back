import pytest
from sqlalchemy.pool import StaticPool

from app import create_app
from app.config import Config
from steeltech_db.extensions import db
from steeltech_db.models.user import User


class TestConfig(Config):
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


@pytest.fixture
def app():
    app = create_app(TestConfig)
    with app.app_context():
        db.create_all()
        user = User(username="admin")
        user.set_password("123456")
        db.session.add(user)
        db.session.commit()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()
