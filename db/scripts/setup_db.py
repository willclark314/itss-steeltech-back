"""创建 MySQL 数据库（若不存在）。"""

from steeltech_db.config import BaseConfig, load_backend_dotenv

load_backend_dotenv()
BaseConfig.refresh_from_env()


def main():
    import pymysql

    from steeltech_db.database_url import mysql_params_from_uri

    if BaseConfig.DATABASE_BACKEND != "mysql":
        print("当前非 MySQL 模式，跳过建库")
        return

    params = mysql_params_from_uri(BaseConfig.SQLALCHEMY_DATABASE_URI)

    conn = pymysql.connect(
        host=params["MYSQL_HOST"],
        port=int(params["MYSQL_PORT"]),
        user=params["MYSQL_USER"],
        password=params["MYSQL_PASSWORD"],
        charset="utf8mb4",
    )
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE IF NOT EXISTS `{params['MYSQL_DATABASE']}` "
                "DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
            )
        conn.commit()
        print(f"数据库 `{params['MYSQL_DATABASE']}` 已就绪")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
