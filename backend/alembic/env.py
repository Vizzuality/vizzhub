"""Alembic migration environment."""

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.database import Base
from app.core.models.job import Job
from app.core.models.functional_area import FunctionalAreaDB  # noqa: F401
from app.core.models.link import LinkDB  # noqa: F401
from app.core.models.program import ProgramDB  # noqa: F401
from app.core.models.rate import RateDB  # noqa: F401
from app.modules.scorecard.models.metrics import MetricsDB
from app.core.models.project import ProjectDB
from app.modules.iso.models import AccessSnapshotDB, AccessReviewDB, AccessReviewActionDB  # noqa: F401
from app.modules.tracker.models import (  # noqa: F401
    AnonymousFeedbackDB, BudgetLineDB, InvoiceDB, NonStaffCostDB, ProgressReportDB,
    ReportDB, ReportPartDB, ReportingPeriodDB, TrackerProjectSettingsDB,
)

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

database_url = os.environ.get("DATABASE_URL")
if database_url:
    config.set_main_option("sqlalchemy.url", database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Run migrations in 'online' mode."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
