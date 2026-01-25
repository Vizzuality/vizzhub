import pytest
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.config import ConfigParameter
from scripts.seed_config_parameters import seed_config_parameters


@pytest.mark.asyncio
async def test_seed_config_parameters_populates_table(db_session: AsyncSession):
    """Test that seed script populates config_parameters table."""
    # Clear table first
    await db_session.execute(delete(ConfigParameter))
    await db_session.commit()

    # Run seed
    await seed_config_parameters(db_session)

    # Verify data
    result = await db_session.execute(
        select(func.count()).select_from(ConfigParameter)
    )
    count = result.scalar()
    assert count == 76  # Total parameters from CSV (includes DORA metrics + milestones target + test_maturity/architecture/pm_satisfaction targets)

    # Verify specific parameter
    result = await db_session.execute(
        select(ConfigParameter).where(ConfigParameter.name == "DefDensity_t")
    )
    param = result.scalar_one()
    assert param.category == "Targets"
    assert param.value == 3.00
    assert param.unit == "%"


@pytest.mark.asyncio
async def test_seed_config_parameters_is_idempotent(db_session: AsyncSession):
    """Test that running seed twice doesn't duplicate data."""
    # Clear table first
    await db_session.execute(delete(ConfigParameter))
    await db_session.commit()

    # Run seed twice
    await seed_config_parameters(db_session)
    await seed_config_parameters(db_session)

    # Verify same number of records
    result = await db_session.execute(
        select(func.count()).select_from(ConfigParameter)
    )
    count = result.scalar()
    assert count == 76
