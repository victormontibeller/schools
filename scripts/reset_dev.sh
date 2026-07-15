#!/usr/bin/env sh
set -eu

if [ "${CONFIRM_RESET_DEV:-}" != "RESET" ]; then
    printf 'Esta operação apaga schools_db, schools_test_db e toda a mídia local. Digite RESET: '
    read -r confirmation
    [ "$confirmation" = "RESET" ] || { echo "Reset cancelado."; exit 1; }
fi

if [ -z "${DEV_PLATFORM_ADMIN_PASSWORD:-}" ] || [ -z "${DEV_DEMO_ADMIN_PASSWORD:-}" ]; then
    echo "Defina DEV_PLATFORM_ADMIN_PASSWORD e DEV_DEMO_ADMIN_PASSWORD antes do reset."
    exit 1
fi
export DEV_PLATFORM_ADMIN_PASSWORD DEV_DEMO_ADMIN_PASSWORD

if command -v docker >/dev/null 2>&1; then
    docker compose stop app worker beat >/dev/null 2>&1 || true
fi

db_host="${DB_HOST:-localhost}"
db_port="${DB_PORT:-5432}"
db_user="${DB_USER:-postgres}"
export PGPASSWORD="${DB_PASSWORD:-postgres}"

if command -v psql >/dev/null 2>&1; then
    for database in schools_db schools_test_db; do
        psql -h "$db_host" -p "$db_port" -U "$db_user" -d postgres \
            -v ON_ERROR_STOP=1 -c "DROP DATABASE IF EXISTS ${database} WITH (FORCE)"
        psql -h "$db_host" -p "$db_port" -U "$db_user" -d postgres \
            -v ON_ERROR_STOP=1 -c "CREATE DATABASE ${database}"
    done
else
    DB_HOST="$db_host" DB_PORT="$db_port" DB_USER="$db_user" ./.venv/bin/python -c '
import os
import psycopg2
from psycopg2 import sql

connection = psycopg2.connect(
    dbname="postgres",
    host=os.environ["DB_HOST"],
    port=os.environ["DB_PORT"],
    user=os.environ["DB_USER"],
    password=os.environ.get("PGPASSWORD", ""),
)
connection.autocommit = True
with connection.cursor() as cursor:
    for database in ("schools_db", "schools_test_db"):
        cursor.execute(
            sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(database))
        )
        cursor.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
connection.close()
'
fi

mkdir -p media/public media/private
find media/public media/private -mindepth 1 -delete

./.venv/bin/python manage.py migrate_schemas --shared
./.venv/bin/python manage.py seed_dev
echo "Ambiente de desenvolvimento reinicializado."
