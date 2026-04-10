"""Tests for mcp_server.data.iso — registry queries."""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.iso_docs.models import RegistryTypeDB


@pytest_asyncio.fixture
async def seed_registry_types(db_session: AsyncSession) -> list[RegistryTypeDB]:
    rt1 = RegistryTypeDB(
        name="Incident Register",
        slug="incident-register",
        description="Security incidents per ISO 27001 A.16",
        is_yearly=True,
        schema=[
            {"key": "number", "label": "Number", "type": "string", "required": True},
            {"key": "date", "label": "Date", "type": "date"},
            {"key": "severity", "label": "Severity", "type": "select",
             "options": ["Critical", "High", "Medium", "Low"]},
        ],
    )
    rt2 = RegistryTypeDB(
        name="Risk Treatment Plan",
        slug="risk-treatment-plan",
        description="Risk treatment actions per ISO 27001 6.1.3",
        is_yearly=False,
        schema=[
            {"key": "risk", "label": "Risk", "type": "string", "required": True},
            {"key": "treatment", "label": "Treatment", "type": "string"},
        ],
    )
    db_session.add_all([rt1, rt2])
    await db_session.commit()
    return [rt1, rt2]


@pytest.mark.asyncio
async def test_get_registry_types_returns_all(
    db_session: AsyncSession, seed_registry_types: list[RegistryTypeDB],
) -> None:
    from mcp_server.data.iso import get_registry_types

    result = await get_registry_types(db_session)
    assert len(result) == 2
    slugs = [rt.slug for rt in result]
    assert "incident-register" in slugs
    assert "risk-treatment-plan" in slugs


@pytest.mark.asyncio
async def test_get_registry_types_ordered_by_name(
    db_session: AsyncSession, seed_registry_types: list[RegistryTypeDB],
) -> None:
    from mcp_server.data.iso import get_registry_types

    result = await get_registry_types(db_session)
    names = [rt.name for rt in result]
    assert names == sorted(names)
