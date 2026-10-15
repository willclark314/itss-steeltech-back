"""初始化 SQLite 开发数据库。"""

from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
load_dotenv(Path(__file__).resolve().parents[1].parent / ".env")


def main() -> None:
    import sys

    backend_root = Path(__file__).resolve().parents[1].parent
    sys.path.insert(0, str(backend_root))

    from app import create_app
    from app.config import Config
    from steeltech_db.seed import bootstrap_sqlite_file

    target = Config.SQLITE_DATABASE_PATH
    bootstrap_sqlite_file(target)
    print(f"SQLite 数据库: {target}")

    app = create_app()

    with app.app_context():
        from steeltech_db.extensions import db
        from steeltech_db.models import ContactForm, Personnel, Project, Role

        print(f"- 人员: {Personnel.query.count()} 条")
        print(f"- 角色: {Role.query.count()} 条")
        print(f"- 项目: {Project.query.count()} 条")
        print(f"- 联系单: {ContactForm.query.count()} 条")


if __name__ == "__main__":
    main()
