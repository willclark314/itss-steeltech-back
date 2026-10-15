from pathlib import Path

from flask import Flask, send_from_directory

# 必须在导入 Config 之前加载 .env，否则类属性会按空环境解析成默认 SQLite
from steeltech_db.config import load_backend_dotenv

load_backend_dotenv()

from app.config import Config
from app.extensions import cors, jwt
from app.routes.auth import auth_bp
from app.routes.backup import backup_bp
from app.routes.db_migrate import db_migrate_bp
from app.routes.change_orders import change_orders_bp
from app.routes.contacts import contacts_bp
from app.routes.design_team_schedule import design_team_schedule_bp
from app.routes.design_drawing_issue_plan import design_drawing_issue_plan_bp
from app.routes.detail_team_schedule import detail_team_schedule_bp
from app.routes.drawing_issue_plan import drawing_issue_plan_bp
from app.routes.leave import leave_bp
from app.routes.monthly_rest import monthly_rest_bp
from app.routes.permissions import permissions_bp
from app.routes.personnel import personnel_bp
from app.routes.projects import projects_bp
from app.routes.roles import roles_bp
from app.routes.navigation import navigation_bp
from app.routes.system import system_bp
from app.routes.tags import tags_bp
from app.routes.temp_tasks import temp_tasks_bp
from app.routes.director_interview import director_interview_bp
from app.routes.monthly_training import monthly_training_bp
from app.routes.file_system import file_system_bp
from app.routes.project_models import project_models_bp
from app.routes.settlement import settlement_bp
from app.routes.weekly_meeting import weekly_meeting_bp
from steeltech_db.extensions import db, migrate
from steeltech_db.seed import bootstrap_sqlite_file, ensure_dev_users, ensure_schema, seed_if_empty


def create_app(config_class: type[Config] = Config) -> Flask:
    load_backend_dotenv()
    # 再次按当前环境刷新，覆盖「先 import、后改环境变量」的场景
    if hasattr(config_class, "refresh_from_env"):
        config_class.refresh_from_env()

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
    app.register_blueprint(design_team_schedule_bp, url_prefix="/api/design-team-schedule")
    app.register_blueprint(detail_team_schedule_bp, url_prefix="/api/detail-team-schedule")
    app.register_blueprint(design_drawing_issue_plan_bp, url_prefix="/api/design-drawing-issue-plan")
    app.register_blueprint(drawing_issue_plan_bp, url_prefix="/api/drawing-issue-plan")
    app.register_blueprint(contacts_bp, url_prefix="/api/contacts")
    app.register_blueprint(change_orders_bp, url_prefix="/api/change-orders")
    app.register_blueprint(tags_bp, url_prefix="/api/tags")
    app.register_blueprint(temp_tasks_bp, url_prefix="/api/temp-tasks")
    app.register_blueprint(monthly_rest_bp, url_prefix="/api/monthly-rest")
    app.register_blueprint(leave_bp, url_prefix="/api/leave")
    app.register_blueprint(system_bp, url_prefix="/api/system")
    app.register_blueprint(navigation_bp, url_prefix="/api/system")
    app.register_blueprint(backup_bp, url_prefix="/api/system/backup")
    app.register_blueprint(db_migrate_bp, url_prefix="/api/system/db-migrate")
    app.register_blueprint(settlement_bp, url_prefix="/api/settlement")
    app.register_blueprint(project_models_bp, url_prefix="/api/project-models")
    app.register_blueprint(weekly_meeting_bp, url_prefix="/api/weekly-meetings")
    app.register_blueprint(director_interview_bp, url_prefix="/api/director-interviews")
    app.register_blueprint(monthly_training_bp, url_prefix="/api/monthly-trainings")
    app.register_blueprint(file_system_bp, url_prefix="/api/file-system")

    @app.get("/api/health")
    def health():
        return {"status": "ok"}

    datas_root = Path(__file__).resolve().parents[1] / "datas"

    @app.get("/datas/<path:file_path>")
    def serve_datas(file_path: str):
        return send_from_directory(datas_root, file_path)

    contact_pdf_root = Path(app.config["CONTACT_PDF_STORAGE_ROOT"])
    contact_attachment_root = Path(app.config["CONTACT_ATTACHMENT_STORAGE_ROOT"])

    @app.get("/api/contact-pdfs/<path:file_path>")
    def serve_contact_pdfs(file_path: str):
        normalized_path = file_path.replace("\\", "/")
        return send_from_directory(str(contact_pdf_root), normalized_path)

    @app.get("/api/contact-attachments/<path:file_path>")
    def serve_contact_attachments(file_path: str):
        normalized_path = file_path.replace("\\", "/")
        attachment_file = contact_attachment_root / Path(normalized_path)
        if attachment_file.is_file():
            return send_from_directory(str(contact_attachment_root), normalized_path)
        legacy_file = contact_pdf_root / Path(normalized_path)
        if legacy_file.is_file():
            return send_from_directory(str(contact_pdf_root), normalized_path)
        return send_from_directory(str(contact_attachment_root), normalized_path)

    weekly_meeting_image_root = Path(app.config["WEEKLY_MEETING_IMAGE_ROOT"])
    weekly_meeting_scan_root = Path(app.config["WEEKLY_MEETING_SCAN_ROOT"])

    @app.get("/api/weekly-meeting-images/<path:file_path>")
    def serve_weekly_meeting_images(file_path: str):
        normalized_path = file_path.replace("\\", "/")
        return send_from_directory(str(weekly_meeting_image_root), normalized_path)

    @app.get("/api/weekly-meeting-scans/<path:file_path>")
    def serve_weekly_meeting_scans(file_path: str):
        normalized_path = file_path.replace("\\", "/")
        return send_from_directory(str(weekly_meeting_scan_root), normalized_path)

    director_interview_image_root = Path(app.config["DIRECTOR_INTERVIEW_IMAGE_ROOT"])

    @app.get("/api/director-interview-images/<path:file_path>")
    def serve_director_interview_images(file_path: str):
        normalized_path = file_path.replace("\\", "/")
        return send_from_directory(str(director_interview_image_root), normalized_path)

    change_order_pdf_root = Path(app.config["CHANGE_ORDER_PDF_STORAGE_ROOT"])

    @app.get("/api/change-order-pdfs/<path:file_path>")
    def serve_change_order_pdfs(file_path: str):
        normalized_path = file_path.replace("\\", "/")
        return send_from_directory(str(change_order_pdf_root), normalized_path)

    monthly_training_file_root = Path(app.config["MONTHLY_TRAINING_FILE_ROOT"])

    @app.get("/api/monthly-training-files/<path:file_path>")
    def serve_monthly_training_files(file_path: str):
        normalized_path = file_path.replace("\\", "/")
        return send_from_directory(str(monthly_training_file_root), normalized_path)

    with app.app_context():
        ensure_schema(app)
        seed_if_empty(app)
        # 生产/开发均需保证 admin/user 对应人员与角色绑定存在
        ensure_dev_users(app)
        # 初始化备份调度器（非阻塞）
        from app.services.backup_service import BackupService
        BackupService().init_scheduler(app)

    return app
