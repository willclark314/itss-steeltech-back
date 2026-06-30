from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, send_from_directory

from app.config import Config
from app.extensions import cors, jwt
from app.routes.auth import auth_bp
from app.routes.backup import backup_bp
from app.routes.contacts import contacts_bp
from app.routes.leave import leave_bp
from app.routes.monthly_rest import monthly_rest_bp
from app.routes.permissions import permissions_bp
from app.routes.personnel import personnel_bp
from app.routes.projects import projects_bp
from app.routes.roles import roles_bp
from app.routes.system import system_bp
from steeltech_db.extensions import db, migrate
from steeltech_db.seed import bootstrap_sqlite_file, ensure_schema, seed_if_empty


def create_app(config_class: type[Config] = Config) -> Flask:
    load_dotenv()

    app = Flask(__name__)
    app.config.from_object(config_class)

    if app.config.get("DATABASE_BACKEND", "sqlite") == "sqlite":
        bootstrap_sqlite_file(config_class.SQLITE_DATABASE_PATH)

    db.init_app(app)
    jwt.init_app(app)
    migrate.init_app(app, db)
    cors.init_app(
        app,
        resources={r"/api/*": {"origins": app.config["CORS_ORIGINS"]}},
        supports_credentials=True,
    )

    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(personnel_bp, url_prefix="/api/personnel")
    app.register_blueprint(permissions_bp, url_prefix="/api/permissions")
    app.register_blueprint(roles_bp, url_prefix="/api/roles")
    app.register_blueprint(projects_bp, url_prefix="/api/projects")
    app.register_blueprint(contacts_bp, url_prefix="/api/contacts")
    app.register_blueprint(monthly_rest_bp, url_prefix="/api/monthly-rest")
    app.register_blueprint(leave_bp, url_prefix="/api/leave")
    app.register_blueprint(system_bp, url_prefix="/api/system")
    app.register_blueprint(backup_bp, url_prefix="/api/system/backup")

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    datas_root = Path(__file__).resolve().parents[1] / "datas"

    @app.get("/datas/<path:file_path>")
    def serve_datas(file_path: str):
        return send_from_directory(datas_root, file_path)

    contact_pdf_root = Path(app.config["CONTACT_PDF_STORAGE_ROOT"])

    @app.get("/api/contact-pdfs/<path:file_path>")
    def serve_contact_pdfs(file_path: str):
        return send_from_directory(contact_pdf_root, file_path)

    with app.app_context():
        ensure_schema(app)
        seed_if_empty(app)
        # 初始化备份调度器（非阻塞）
        from app.services.backup_service import BackupService
        BackupService().init_scheduler(app)

    return app
