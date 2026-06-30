#!/bin/sh
set -e

if [ "${DATABASE_BACKEND}" = "mysql" ]; then
  echo "等待 MySQL 就绪并创建数据库..."
  python /itss-steeltech-db/scripts/setup_db.py
fi

exec gunicorn --bind 0.0.0.0:5000 --workers 2 --timeout 120 run:app
