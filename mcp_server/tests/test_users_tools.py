"""Tests for MCP Users tools — tool response formatting via call_tool."""

import json
from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.functional_area import FunctionalAreaDB
from app.core.models.rate import RateDB
from app.core.models.role import RoleDB, UserRoleDB
from app.core.models.user import UserDB
from mcp_server.data.base import override_session
from mcp_server.server import create_mcp_server


def _parse_tool_result(result) -> dict | list:
    content_blocks = result[0]
    return json.loads(content_blocks[0].text)


@pytest_asyncio.fixture
async def seed_users(db_session: AsyncSession) -> dict:
    """Seed users with functional areas, rates, and roles."""
    fa = FunctionalAreaDB(name="Frontend Developer")
    db_session.add(fa)
    await db_session.flush()

    rate = RateDB(code="A", value=Decimal("150.00"))
    db_session.add(rate)
    await db_session.flush()

    role = RoleDB(name="user", description="Basic user")
    db_session.add(role)
    await db_session.flush()

    user = UserDB(
        email="alice@vizzuality.com",
        first_name="Alice",
        last_name="Smith",
        functional_area_id=fa.id,
        rate_id=rate.id,
        dedication=Decimal("1.00"),
        active=True,
        requires_project_reporting=True,
    )
    inactive_user = UserDB(
        email="bob@vizzuality.com",
        name="Bob Jones",
        active=False,
    )
    db_session.add_all([user, inactive_user])
    await db_session.flush()

    db_session.add(UserRoleDB(user_id=user.id, role_id=role.id))
    await db_session.commit()

    return {
        "user_id": str(user.id),
        "inactive_user_id": str(inactive_user.id),
    }


@pytest.mark.asyncio
async def test_users_get_team(db_session, seed_users) -> None:
    server = create_mcp_server()
    async with override_session(db_session):
        result = await server.call_tool("users_get_team", {})
    data = _parse_tool_result(result)
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["name"] == "Alice Smith"
    assert data[0]["functional_area"] == "Frontend Developer"
    assert data[0]["roles"] == ["user"]


@pytest.mark.asyncio
async def test_users_get_team_include_inactive(db_session, seed_users) -> None:
    server = create_mcp_server()
    async with override_session(db_session):
        result = await server.call_tool(
            "users_get_team", {"active_only": False},
        )
    data = _parse_tool_result(result)
    assert len(data) == 2


@pytest.mark.asyncio
async def test_users_get_team_filter_fa(db_session, seed_users) -> None:
    server = create_mcp_server()
    async with override_session(db_session):
        result = await server.call_tool(
            "users_get_team", {"functional_area": "Frontend Developer"},
        )
    data = _parse_tool_result(result)
    assert len(data) == 1
    assert data[0]["functional_area"] == "Frontend Developer"


@pytest.mark.asyncio
async def test_users_get_detail(db_session, seed_users) -> None:
    server = create_mcp_server()
    async with override_session(db_session):
        result = await server.call_tool(
            "users_get_detail", {"user_id": seed_users["user_id"]},
        )
    data = _parse_tool_result(result)
    assert data["name"] == "Alice Smith"
    assert data["rate_code"] == "A"
    assert data["rate_value"] == 150.0
    assert data["roles"] == ["user"]


@pytest.mark.asyncio
async def test_users_get_detail_not_found(db_session, seed_users) -> None:
    server = create_mcp_server()
    async with override_session(db_session):
        result = await server.call_tool(
            "users_get_detail",
            {"user_id": "00000000-0000-0000-0000-000000000000"},
        )
    data = _parse_tool_result(result)
    assert "error" in data


@pytest.mark.asyncio
async def test_users_get_functional_areas(db_session, seed_users) -> None:
    server = create_mcp_server()
    async with override_session(db_session):
        result = await server.call_tool("users_get_functional_areas", {})
    data = _parse_tool_result(result)
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["name"] == "Frontend Developer"


@pytest.mark.asyncio
async def test_users_get_rates(db_session, seed_users) -> None:
    server = create_mcp_server()
    async with override_session(db_session):
        result = await server.call_tool("users_get_rates", {})
    data = _parse_tool_result(result)
    assert isinstance(data, list)
    assert len(data) == 1
    assert data[0]["code"] == "A"
    assert data[0]["value"] == 150.0
