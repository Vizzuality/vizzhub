#!/bin/sh
set -e

# If alembic_version table doesn't exist, stamp at the last migration
# that was already applied via create_all before alembic was introduced.
if [ -n "$DATABASE_URL" ]; then
    SYNC_URL=$(echo "$DATABASE_URL" | sed 's/+asyncpg//')
    python -c "
from sqlalchemy import create_engine, text
import sys
engine = create_engine('$SYNC_URL')
with engine.connect() as conn:
    result = conn.execute(text(
        \"SELECT EXISTS(SELECT 1 FROM information_schema.tables WHERE table_name='alembic_version')\"
    ))
    exists = result.scalar()
    if not exists:
        print('alembic_version not found, stamping at 012_add_users_table')
        sys.exit(1)
    else:
        result = conn.execute(text('SELECT version_num FROM alembic_version'))
        row = result.fetchone()
        print(f'alembic_version found: {row[0] if row else \"empty\"}')
engine.dispose()
" || alembic stamp 012_add_users_table

    alembic upgrade head
fi

exec uvicorn app.main:app --host 0.0.0.0 --port 8000
