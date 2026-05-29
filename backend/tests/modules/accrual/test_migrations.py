"""Migration smoke tests — verify columns/tables/constraints exist."""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_projects_does_not_have_locked_fx_rate(db_session: AsyncSession) -> None:
    """Migration 081 dropped projects.locked_fx_rate."""
    result = await db_session.execute(
        text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'projects' AND column_name = 'locked_fx_rate'"
        )
    )
    assert result.one_or_none() is None, "projects.locked_fx_rate must be dropped"


@pytest.mark.asyncio
async def test_accrual_periods_table_exists(db_session: AsyncSession) -> None:
    result = await db_session.execute(text("SELECT to_regclass('public.accrual_periods')"))
    assert result.scalar() is not None


@pytest.mark.asyncio
async def test_accrual_periods_does_not_have_fx_rates(db_session: AsyncSession) -> None:
    """Migration 081 dropped accrual_periods.fx_rates."""
    result = await db_session.execute(
        text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'accrual_periods' AND column_name = 'fx_rates'"
        )
    )
    assert result.one_or_none() is None, "accrual_periods.fx_rates must be dropped"


@pytest.mark.asyncio
async def test_accrual_periods_partial_unique_one_open(db_session: AsyncSession) -> None:
    result = await db_session.execute(
        text(
            "SELECT indexdef FROM pg_indexes "
            "WHERE tablename = 'accrual_periods' AND indexname = 'uq_accrual_periods_one_open'"
        )
    )
    indexdef = result.scalar()
    assert indexdef is not None
    assert "WHERE" in indexdef and "open" in indexdef.lower()


@pytest.mark.asyncio
async def test_accrual_periods_start_date_unique(db_session: AsyncSession) -> None:
    result = await db_session.execute(
        text(
            "SELECT conname FROM pg_constraint "
            "WHERE conrelid = 'accrual_periods'::regclass "
            "AND conname = 'uq_accrual_periods_start_date'"
        )
    )
    assert result.scalar() == "uq_accrual_periods_start_date"


@pytest.mark.asyncio
async def test_project_accrual_cells_table_exists(db_session: AsyncSession) -> None:
    result = await db_session.execute(text("SELECT to_regclass('public.project_accrual_cells')"))
    assert result.scalar() is not None


@pytest.mark.asyncio
async def test_project_accrual_cells_does_not_have_frozen_rate(db_session: AsyncSession) -> None:
    """Migration 081 dropped project_accrual_cells.frozen_rate."""
    result = await db_session.execute(
        text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'project_accrual_cells' AND column_name = 'frozen_rate'"
        )
    )
    assert result.one_or_none() is None, "project_accrual_cells.frozen_rate must be dropped"


@pytest.mark.asyncio
async def test_project_accrual_cells_unique_line_month(db_session: AsyncSession) -> None:
    """Migration 083 dropped the per-project unique (incompatible with multiple
    lines on one project) and replaced it with a per-line unique."""
    dropped = await db_session.execute(
        text(
            "SELECT conname FROM pg_constraint "
            "WHERE conrelid = 'project_accrual_cells'::regclass "
            "AND conname = 'uq_accrual_cells_project_month'"
        )
    )
    assert dropped.scalar() is None, "legacy uq_accrual_cells_project_month must be dropped"

    result = await db_session.execute(
        text(
            "SELECT conname FROM pg_constraint "
            "WHERE conrelid = 'project_accrual_cells'::regclass "
            "AND conname = 'uq_accrual_cells_line_month'"
        )
    )
    assert result.scalar() == "uq_accrual_cells_line_month"


@pytest.mark.asyncio
async def test_project_accrual_cells_month_check(db_session: AsyncSession) -> None:
    result = await db_session.execute(
        text(
            "SELECT conname FROM pg_constraint "
            "WHERE conrelid = 'project_accrual_cells'::regclass "
            "AND conname = 'ck_accrual_cells_month_range'"
        )
    )
    assert result.scalar() == "ck_accrual_cells_month_range"
