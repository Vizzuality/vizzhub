"""Tests for config API endpoints."""

import pytest
import pytest_asyncio
from decimal import Decimal
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.config import ConfigParameter


@pytest_asyncio.fixture
async def seeded_db(db_session: AsyncSession):
    """Fixture that seeds the database with config parameters."""
    params = [
        ConfigParameter(
            category="Targets",
            name="DefDensity_t",
            value=Decimal("3.0000"),
            unit="defects/100 tasks",
        ),
        # Global Weights (must sum to 1.0)
        ConfigParameter(
            category="Global Weights",
            name="W_time",
            value=Decimal("0.1250"),
        ),
        ConfigParameter(
            category="Global Weights",
            name="W_cost",
            value=Decimal("0.1250"),
        ),
        ConfigParameter(
            category="Global Weights",
            name="W_quality",
            value=Decimal("0.1250"),
        ),
        ConfigParameter(
            category="Global Weights",
            name="W_value",
            value=Decimal("0.1250"),
        ),
        ConfigParameter(
            category="Global Weights",
            name="W_satisfaction",
            value=Decimal("0.1250"),
        ),
        ConfigParameter(
            category="Global Weights",
            name="W_flow",
            value=Decimal("0.1250"),
        ),
        ConfigParameter(
            category="Global Weights",
            name="W_engineering",
            value=Decimal("0.1250"),
        ),
        ConfigParameter(
            category="Global Weights",
            name="W_risk",
            value=Decimal("0.1250"),
        ),
        # Quality Weights (must sum to 1.0)
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
        # Time Weights (must sum to 1.0)
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
    ]

    for param in params:
        db_session.add(param)
    await db_session.commit()

    return db_session


@pytest.mark.asyncio
async def test_get_config_parameters(client: AsyncClient, seeded_db: AsyncSession):
    """Test GET /api/config/parameters returns all grouped parameters."""
    response = await client.get("/api/config/parameters")

    assert response.status_code == 200
    data = response.json()

    # Verify structure
    assert "Targets" in data
    assert "Global Weights" in data
    assert "Quality Weights" in data

    # Verify specific parameter
    targets = data["Targets"]
    defect_param = next(p for p in targets if p["name"] == "DefDensity_t")
    assert defect_param["value"] == "3.0000"
    assert defect_param["unit"] == "defects/100 tasks"
    assert defect_param["category"] == "Targets"


@pytest.mark.asyncio
async def test_update_config_parameters(client: AsyncClient, seeded_db: AsyncSession):
    """Test PATCH /api/config/parameters updates values."""
    updates = [{"name": "DefDensity_t", "value": "2.5000"}]

    response = await client.patch("/api/config/parameters", json=updates)

    assert response.status_code == 200
    assert response.json() == {"status": "success"}

    # Verify update persisted
    response = await client.get("/api/config/parameters")
    targets = response.json()["Targets"]
    defect_param = next(p for p in targets if p["name"] == "DefDensity_t")
    assert defect_param["value"] == "2.5000"

    # Restore original
    await client.patch(
        "/api/config/parameters", json=[{"name": "DefDensity_t", "value": "3.0000"}]
    )


@pytest.mark.asyncio
async def test_update_config_parameters_rejects_invalid_weights(
    client: AsyncClient, seeded_db: AsyncSession
):
    """Test PATCH rejects updates that break weight validation."""
    updates = [{"name": "W_time_spi", "value": "1.0000"}]  # Breaks Time Weights sum

    response = await client.patch("/api/config/parameters", json=updates)

    assert response.status_code == 400
    detail = response.json()["detail"]
    # Check structured error response
    if isinstance(detail, dict):
        assert "Weight validation failed" in detail["message"]
    else:
        assert "Weight validation failed" in detail


@pytest.mark.asyncio
async def test_validate_config(client: AsyncClient, seeded_db: AsyncSession):
    """Test GET /api/config/validate returns validation status."""
    response = await client.get("/api/config/validate")

    assert response.status_code == 200
    data = response.json()

    assert "valid" in data
    assert "errors" in data
    assert data["valid"] is True
    assert len(data["errors"]) == 0
