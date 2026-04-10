"""Tests for mcp_server.data.iso — registry queries."""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.iso_docs.models import IsoDocNodeDB, RegistryRowDB, RegistryTypeDB


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


@pytest_asyncio.fixture
async def seed_registry_with_rows(
    db_session: AsyncSession, seed_registry_types: list[RegistryTypeDB],
) -> dict:
    rt = seed_registry_types[0]  # incident-register, is_yearly=True
    node = IsoDocNodeDB(
        title="Incident Register",
        slug="incident-register",
        type="registry",
        registry_type_id=rt.id,
    )
    db_session.add(node)
    await db_session.flush()

    rows = [
        RegistryRowDB(
            node_id=node.id, year=2026, row_index=0,
            data={"number": "INC-001", "date": "2026-01-15", "severity": "High"},
        ),
        RegistryRowDB(
            node_id=node.id, year=2026, row_index=1,
            data={"number": "INC-002", "date": "2026-03-22", "severity": "Low"},
        ),
        RegistryRowDB(
            node_id=node.id, year=2025, row_index=0,
            data={"number": "INC-003", "date": "2025-11-01", "severity": "Medium"},
        ),
    ]
    db_session.add_all(rows)
    await db_session.commit()
    return {"registry_type": rt, "node": node, "rows": rows}


@pytest.mark.asyncio
async def test_resolve_registry_node_found(
    db_session: AsyncSession, seed_registry_with_rows: dict,
) -> None:
    from mcp_server.data.iso import resolve_registry_node

    rt, node_id = await resolve_registry_node(db_session, "incident-register")
    assert rt.slug == "incident-register"
    assert node_id == seed_registry_with_rows["node"].id


@pytest.mark.asyncio
async def test_resolve_registry_node_not_found(db_session: AsyncSession) -> None:
    from mcp_server.data.iso import resolve_registry_node

    with pytest.raises(ValueError, match="not found"):
        await resolve_registry_node(db_session, "nonexistent-slug")


@pytest.mark.asyncio
async def test_get_registry_rows_filters_by_year(
    db_session: AsyncSession, seed_registry_with_rows: dict,
) -> None:
    from mcp_server.data.iso import get_registry_rows

    node_id = seed_registry_with_rows["node"].id
    rows = await get_registry_rows(db_session, node_id, year=2026)
    assert len(rows) == 2
    numbers = [r.data["number"] for r in rows]
    assert "INC-001" in numbers
    assert "INC-002" in numbers


@pytest.mark.asyncio
async def test_get_registry_rows_all_years(
    db_session: AsyncSession, seed_registry_with_rows: dict,
) -> None:
    from mcp_server.data.iso import get_registry_rows

    node_id = seed_registry_with_rows["node"].id
    rows = await get_registry_rows(db_session, node_id, year=None)
    assert len(rows) == 3


@pytest.mark.asyncio
async def test_get_registry_rows_ordered_by_index(
    db_session: AsyncSession, seed_registry_with_rows: dict,
) -> None:
    from mcp_server.data.iso import get_registry_rows

    node_id = seed_registry_with_rows["node"].id
    rows = await get_registry_rows(db_session, node_id, year=2026)
    indices = [r.row_index for r in rows]
    assert indices == sorted(indices)
