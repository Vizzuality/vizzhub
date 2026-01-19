import pytest
import pytest_asyncio
from decimal import Decimal
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.config import ConfigParameter
from app.services.config_service import ConfigService


@pytest_asyncio.fixture
async def seeded_db(db_session: AsyncSession):
    """Fixture that seeds the database with config parameters."""
    # Seed minimal data needed for tests
    params = [
        ConfigParameter(
            category="Targets",
            name="DefDensity_t",
            value=Decimal("3.00"),
            unit="defects/100 tasks",
        ),
        ConfigParameter(
            category="Time Weights",
            name="W_time_spi",
            value=Decimal("0.60"),
        ),
        ConfigParameter(
            category="Time Weights",
            name="W_time_milestones",
            value=Decimal("0.40"),
        ),
        ConfigParameter(
            category="Quality Weights",
            name="W_def",
            value=Decimal("0.05"),
        ),
        ConfigParameter(
            category="Quality Weights",
            name="W_esc",
            value=Decimal("0.45"),
        ),
        ConfigParameter(
            category="Quality Weights",
            name="W_mttr",
            value=Decimal("0.30"),
        ),
        ConfigParameter(
            category="Quality Weights",
            name="W_sev1",
            value=Decimal("0.20"),
        ),
    ]

    for param in params:
        db_session.add(param)
    await db_session.commit()

    return db_session


@pytest.mark.asyncio
async def test_get_parameter_value(seeded_db: AsyncSession):
    """Test getting a single parameter value by name."""
    db = seeded_db
    value = await ConfigService.get_parameter_value(db, "DefDensity_t")
    assert value == Decimal("3.00")


@pytest.mark.asyncio
async def test_get_parameter_value_not_found(seeded_db: AsyncSession):
    """Test getting non-existent parameter raises error."""
    db = seeded_db
    with pytest.raises(ValueError, match="Parameter.*not found"):
        await ConfigService.get_parameter_value(db, "NonExistent")


@pytest.mark.asyncio
async def test_get_parameters_by_category(seeded_db: AsyncSession):
    """Test getting all parameters in a category."""
    db = seeded_db
    params = await ConfigService.get_parameters_by_category(db, "Time Weights")

    assert "W_time_spi" in params
    assert "W_time_milestones" in params
    assert params["W_time_spi"] == Decimal("0.60")
    assert params["W_time_milestones"] == Decimal("0.40")


@pytest.mark.asyncio
async def test_validate_weight_groups_all_valid(seeded_db: AsyncSession):
    """Test weight validation passes for valid weights."""
    db = seeded_db
    errors = await ConfigService.validate_weight_groups(db)
    assert len(errors) == 0


@pytest.mark.asyncio
async def test_validate_weight_groups_detects_invalid(seeded_db: AsyncSession):
    """Test weight validation detects invalid sum."""
    db = seeded_db
    # Temporarily break Quality Weights (change W_def to 0)
    result = await db.execute(
        select(ConfigParameter).where(ConfigParameter.name == "W_def")
    )
    param = result.scalar_one()
    param.value = Decimal("0")
    await db.commit()

    errors = await ConfigService.validate_weight_groups(db)
    assert len(errors) > 0
    assert any("Quality Weights" in err for err in errors)

    # Restore
    param.value = Decimal("0.05")
    await db.commit()


@pytest.mark.asyncio
async def test_update_parameters(seeded_db: AsyncSession):
    """Test updating multiple parameters."""
    from app.models.config import ConfigParameterUpdate

    db = seeded_db
    updates = [ConfigParameterUpdate(name="DefDensity_t", value=Decimal("2.50"))]

    await ConfigService.update_parameters(db, updates)

    # Verify update
    value = await ConfigService.get_parameter_value(db, "DefDensity_t")
    assert value == Decimal("2.50")

    # Restore original
    updates = [ConfigParameterUpdate(name="DefDensity_t", value=Decimal("3.00"))]
    await ConfigService.update_parameters(db, updates)


@pytest.mark.asyncio
async def test_update_parameters_rejects_invalid_weights(seeded_db: AsyncSession):
    """Test update rejects changes that break weight validation."""
    from app.models.config import ConfigParameterUpdate

    db = seeded_db
    # Try to set W_time_spi to 1.0 (breaks Time Weights sum)
    updates = [ConfigParameterUpdate(name="W_time_spi", value=Decimal("1.00"))]

    with pytest.raises(ValueError, match="Weight validation failed"):
        await ConfigService.update_parameters(db, updates)
