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
