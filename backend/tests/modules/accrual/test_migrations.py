"""Migration smoke tests — verify columns/tables/constraints exist."""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_projects_has_locked_fx_rate(db_session: AsyncSession) -> None:
    result = await db_session.execute(
        text(
            "SELECT column_name, data_type, is_nullable, numeric_precision, numeric_scale "
            "FROM information_schema.columns "
            "WHERE table_name = 'projects' AND column_name = 'locked_fx_rate'"
        )
    )
    row = result.one_or_none()
    assert row is not None, "projects.locked_fx_rate missing"
    assert row.data_type == "numeric"
    assert row.is_nullable == "YES"
    assert row.numeric_precision == 12
    assert row.numeric_scale == 6


@pytest.mark.asyncio
async def test_accrual_periods_table_exists(db_session: AsyncSession) -> None:
    result = await db_session.execute(text("SELECT to_regclass('public.accrual_periods')"))
    assert result.scalar() is not None


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
