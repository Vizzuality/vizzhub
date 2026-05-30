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
async def test_accrual_cells_table_renamed(db_session: AsyncSession) -> None:
    """Migration 084 renamed project_accrual_cells → accrual_cells."""
    assert (
        await db_session.execute(text("SELECT to_regclass('public.accrual_cells')"))
    ).scalar() is not None
    assert (
        await db_session.execute(text("SELECT to_regclass('public.project_accrual_cells')"))
    ).scalar() is None


@pytest.mark.asyncio
async def test_accrual_cells_dropped_project_id(db_session: AsyncSession) -> None:
    """Migration 084 dropped the denormalised project_id; cells are line-keyed."""
    result = await db_session.execute(
        text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = 'accrual_cells' AND column_name = 'project_id'"
        )
    )
    assert result.one_or_none() is None, "accrual_cells.project_id must be dropped"


@pytest.mark.asyncio
async def test_accrual_cells_line_id_not_null(db_session: AsyncSession) -> None:
    result = await db_session.execute(
        text(
            "SELECT is_nullable FROM information_schema.columns "
            "WHERE table_name = 'accrual_cells' AND column_name = 'line_id'"
        )
    )
    assert result.scalar() == "NO", "accrual_cells.line_id must be NOT NULL"


@pytest.mark.asyncio
async def test_accrual_cells_unique_line_month(db_session: AsyncSession) -> None:
    result = await db_session.execute(
        text(
            "SELECT conname FROM pg_constraint "
            "WHERE conrelid = 'accrual_cells'::regclass "
            "AND conname = 'uq_accrual_cells_line_month'"
        )
    )
    assert result.scalar() == "uq_accrual_cells_line_month"


@pytest.mark.asyncio
async def test_accrual_cells_month_check(db_session: AsyncSession) -> None:
    result = await db_session.execute(
        text(
            "SELECT conname FROM pg_constraint "
            "WHERE conrelid = 'accrual_cells'::regclass "
            "AND conname = 'ck_accrual_cells_month_range'"
        )
    )
    assert result.scalar() == "ck_accrual_cells_month_range"


@pytest.mark.asyncio
async def test_import_era_tables_dropped(db_session: AsyncSession) -> None:
    """Migration 084 retired the Excel-import era (aliases + drift findings)."""
    for table in ("accrual_aliases", "accrual_drift_findings"):
        result = await db_session.execute(text(f"SELECT to_regclass('public.{table}')"))
        assert result.scalar() is None, f"{table} must be dropped"
