#!/bin/sh
set -e

_is_mysql_mode() {
  case "${DATABASE_URL}${SQLALCHEMY_DATABASE_URI}" in
    mysql:*|mysql+*) return 0 ;;
  esac
  return 1
}

if _is_mysql_mode; then
  echo "等待 MySQL 就绪并创建数据库..."
  python /itss-steeltech-db/scripts/setup_db.py
fi

exec gunicorn --bind 0.0.0.0:5000 --workers 2 --timeout 120 run:app
