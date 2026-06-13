"""初始化 SQLite 开发数据库。"""

from dotenv import load_dotenv

load_dotenv()

from app import create_app
from app.config import Config
from app.seed import bootstrap_sqlite_file


def main() -> None:
    target = Config.SQLITE_DATABASE_PATH
    bootstrap_sqlite_file(target)
    print(f"SQLite 数据库: {target}")

    app = create_app()

    with app.app_context():
        from app.extensions import db
        from app.models import ContactForm, Personnel, Project, Role

        print(f"- 人员: {Personnel.query.count()} 条")
        print(f"- 角色: {Role.query.count()} 条")
        print(f"- 项目: {Project.query.count()} 条")
        print(f"- 联系单: {ContactForm.query.count()} 条")

        if Config.DATABASE_BACKEND == "mysql":
            db.create_all()
            from app.models.user import User
            import os

            default_username = os.getenv("DEFAULT_ADMIN_USERNAME", "admin")
            default_password = os.getenv("DEFAULT_ADMIN_PASSWORD", "123456")
            user = User.query.filter_by(username=default_username).first()
            if user is None:
                user = User(username=default_username)
                user.set_password(default_password)
                db.session.add(user)
                db.session.commit()
                print(f"已创建 MySQL 管理员: {default_username} / {default_password}")


if __name__ == "__main__":
    main()
