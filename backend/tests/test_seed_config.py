import csv
from pathlib import Path

import pytest
from sqlalchemy import select, func, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.scorecard.models.config import ConfigParameter
from scripts.seed_config_parameters import seed_config_parameters


def get_csv_parameter_count() -> int:
    """Count parameters in CSV file (excluding header)."""
    csv_path = Path(__file__).parent.parent / "seeds" / "config_parameters.csv"
    with open(csv_path) as f:
        return sum(1 for _ in csv.reader(f)) - 1


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
    assert count == get_csv_parameter_count()

    # Verify specific parameter
    result = await db_session.execute(
        select(ConfigParameter).where(ConfigParameter.name == "target_defect_density")
    )
    param = result.scalar_one()
    assert param.category == "Targets"
    assert param.value == pytest.approx(6.00)
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
    assert count == get_csv_parameter_count()
