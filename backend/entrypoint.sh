#!/bin/sh
set -e

# If alembic_version table doesn't exist, stamp at the last migration
# that was already applied via create_all before alembic was introduced.
if [ -n "$DATABASE_URL" ]; then
    python -c "
import os, sys
from sqlalchemy import create_engine, text
url = os.environ['DATABASE_URL'].replace('+asyncpg', '')
engine = create_engine(url)
with engine.connect() as conn:
    result = conn.execute(text(
        \"SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name='alembic_version')\"
    ))
    if not result.scalar():
        sys.exit(1)
engine.dispose()
" || alembic stamp 012_add_users_table

    alembic upgrade head
fi

exec uvicorn app.main:app --host 0.0.0.0 --port 8000
