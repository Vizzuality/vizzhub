import pytest
from decimal import Decimal
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from app.modules.scorecard.models.config import ConfigParameter


@pytest.mark.asyncio
async def test_config_parameter_creation(db_session: AsyncSession):
    """Test creating a config parameter."""
    param = ConfigParameter(
        category="Targets",
        name="DefDensity_t",
        value=Decimal("3.00"),
        unit="defects/100 tasks",
        notes="Target max defect density",
    )
    db_session.add(param)
    await db_session.commit()
    await db_session.refresh(param)

    assert param.id is not None
    assert param.category == "Targets"
    assert param.name == "DefDensity_t"
    assert param.value == Decimal("3.00")
    assert param.unit == "defects/100 tasks"


@pytest.mark.asyncio
async def test_config_parameter_unique_name(db_session: AsyncSession):
    """Test that parameter name is unique."""
    param1 = ConfigParameter(
        category="Targets", name="test_param", value=Decimal("1.0")
    )
    param2 = ConfigParameter(
        category="Targets", name="test_param", value=Decimal("2.0")
    )

    db_session.add(param1)
    await db_session.commit()

    db_session.add(param2)
    with pytest.raises(IntegrityError):
        await db_session.commit()
