"""初始化 SQLite 开发数据库（也可独立运行：python init_db.py）。

与 start.ps1 不同，本脚本提供详细的初始化输出，适合首次搭建开发环境时使用。
"""

from dotenv import load_dotenv

load_dotenv()

from app import create_app
from app.config import Config
from steeltech_db.seed import bootstrap_sqlite_file, ensure_dev_users


def main() -> None:
    target = Config.SQLITE_DATABASE_PATH

    # 1. 创建数据库文件 + 导入 schema.sql（如已存在则跳过）
    bootstrap_sqlite_file(target)

    # 2. 创建 Flask 应用（create_app 内部会执行 ensure_schema + seed_if_empty）
    app = create_app()

    with app.app_context():
        from steeltech_db.extensions import db
        from steeltech_db.models import ContactForm, Personnel, Project, Role

        # 3. 确保开发测试账号存在（DEV001=admin, DEV002=user）
        ensure_dev_users(app)

        # ---------- 汇总输出 ----------
        print(f"\n{'='*50}")
        print(f"数据库初始化完成")
        print(f"  后端: {Config.DATABASE_BACKEND}")
        print(f"  文件: {target}")
        print(f"  人员: {Personnel.query.count()} 条")
        print(f"  角色: {Role.query.count()} 条")
        print(f"  项目: {Project.query.count()} 条")
        print(f"  联系单: {ContactForm.query.count()} 条")

        print(f"{'='*50}\n")


if __name__ == "__main__":
    main()
