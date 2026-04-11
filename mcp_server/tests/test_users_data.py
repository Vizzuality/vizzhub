"""Tests for Users data layer."""

from decimal import Decimal

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.functional_area import FunctionalAreaDB
from app.core.models.rate import RateDB
from app.core.models.role import RoleDB, UserRoleDB
from app.core.models.user import UserDB
from mcp_server.data import users as users_data


@pytest_asyncio.fixture
async def seed_users(db_session: AsyncSession) -> dict:
    """Seed users with functional areas, rates, and roles."""
    fa_fe = FunctionalAreaDB(name="Frontend Developer")
    fa_be = FunctionalAreaDB(name="Backend Developer")
    db_session.add_all([fa_fe, fa_be])
    await db_session.flush()

    rate_a = RateDB(code="A", value=Decimal("150.00"))
    rate_b = RateDB(code="B", value=Decimal("120.00"))
    db_session.add_all([rate_a, rate_b])
    await db_session.flush()

    role_user = RoleDB(name="user", description="Basic user")
    role_manager = RoleDB(name="manager", description="Project manager")
    role_admin = RoleDB(name="admin", description="Administrator")
    db_session.add_all([role_user, role_manager, role_admin])
    await db_session.flush()

    user1 = UserDB(
        email="alice@vizzuality.com",
        first_name="Alice",
        last_name="Smith",
        functional_area_id=fa_fe.id,
        rate_id=rate_a.id,
        dedication=Decimal("1.00"),
        active=True,
        requires_project_reporting=True,
        slack_display_name="alice.smith",
    )
    user2 = UserDB(
        email="bob@vizzuality.com",
        first_name="Bob",
        last_name="Jones",
        functional_area_id=fa_be.id,
        rate_id=rate_b.id,
        dedication=Decimal("0.80"),
        active=True,
        requires_project_reporting=True,
    )
    user3 = UserDB(
        email="charlie@vizzuality.com",
        name="Charlie Brown",
        active=False,
        requires_project_reporting=False,
    )
    db_session.add_all([user1, user2, user3])
    await db_session.flush()

    db_session.add_all([
        UserRoleDB(user_id=user1.id, role_id=role_user.id),
        UserRoleDB(user_id=user2.id, role_id=role_user.id),
        UserRoleDB(user_id=user2.id, role_id=role_manager.id),
        UserRoleDB(user_id=user3.id, role_id=role_admin.id),
    ])
    await db_session.commit()

    return {
        "user1_id": str(user1.id),
        "user2_id": str(user2.id),
        "user3_id": str(user3.id),
        "fa_fe_id": str(fa_fe.id),
        "fa_be_id": str(fa_be.id),
    }


@pytest.mark.asyncio
async def test_get_team_active_only(db_session, seed_users) -> None:
    result = await users_data.get_team(db_session, active_only=True)
    assert len(result) == 2
    names = [u["name"] for u in result]
    assert "Alice Smith" in names
    assert "Bob Jones" in names


@pytest.mark.asyncio
async def test_get_team_includes_inactive(db_session, seed_users) -> None:
    result = await users_data.get_team(db_session, active_only=False)
    assert len(result) == 3
    inactive = [u for u in result if not u["active"]]
    assert len(inactive) == 1
    assert inactive[0]["name"] == "Charlie Brown"


@pytest.mark.asyncio
async def test_get_team_filter_by_fa(db_session, seed_users) -> None:
    result = await users_data.get_team(
        db_session, functional_area="Frontend Developer",
    )
    assert len(result) == 1
    assert result[0]["name"] == "Alice Smith"
    assert result[0]["functional_area"] == "Frontend Developer"


@pytest.mark.asyncio
async def test_get_team_includes_roles(db_session, seed_users) -> None:
    result = await users_data.get_team(db_session, active_only=False)
    bob = next(u for u in result if u["email"] == "bob@vizzuality.com")
    assert sorted(bob["roles"]) == ["manager", "user"]


@pytest.mark.asyncio
async def test_get_team_fields(db_session, seed_users) -> None:
    result = await users_data.get_team(db_session)
    alice = next(u for u in result if u["email"] == "alice@vizzuality.com")
    assert alice["functional_area"] == "Frontend Developer"
    assert alice["rate_code"] == "A"
    assert alice["dedication"] == 1.0
    assert alice["requires_project_reporting"] is True
    assert alice["slack_display_name"] == "alice.smith"


@pytest.mark.asyncio
async def test_get_team_name_fallbacks(db_session, seed_users) -> None:
    result = await users_data.get_team(db_session, active_only=False)
    charlie = next(u for u in result if u["email"] == "charlie@vizzuality.com")
    assert charlie["name"] == "Charlie Brown"


@pytest.mark.asyncio
async def test_get_detail(db_session, seed_users) -> None:
    result = await users_data.get_detail(db_session, seed_users["user1_id"])
    assert result is not None
    assert result["name"] == "Alice Smith"
    assert result["first_name"] == "Alice"
    assert result["last_name"] == "Smith"
    assert result["functional_area"] == "Frontend Developer"
    assert result["rate_code"] == "A"
    assert result["rate_value"] == 150.0
    assert result["dedication"] == 1.0
    assert result["roles"] == ["user"]


@pytest.mark.asyncio
async def test_get_detail_not_found(db_session, seed_users) -> None:
    result = await users_data.get_detail(
        db_session, "00000000-0000-0000-0000-000000000000",
    )
    assert result is None


@pytest.mark.asyncio
async def test_get_detail_no_fa_no_rate(db_session, seed_users) -> None:
    result = await users_data.get_detail(db_session, seed_users["user3_id"])
    assert result is not None
    assert result["functional_area"] is None
    assert result["rate_code"] is None
    assert result["rate_value"] is None
    assert result["dedication"] is None


@pytest.mark.asyncio
async def test_get_functional_areas(db_session, seed_users) -> None:
    result = await users_data.get_functional_areas(db_session)
    assert len(result) == 2
    names = [fa["name"] for fa in result]
    assert "Backend Developer" in names
    assert "Frontend Developer" in names
    assert all("id" in fa for fa in result)


@pytest.mark.asyncio
async def test_get_functional_areas_empty(db_session) -> None:
    result = await users_data.get_functional_areas(db_session)
    assert result == []


@pytest.mark.asyncio
async def test_get_rates(db_session, seed_users) -> None:
    result = await users_data.get_rates(db_session)
    assert len(result) == 2
    assert result[0]["code"] == "A"
    assert result[0]["value"] == 150.0
    assert result[1]["code"] == "B"
    assert result[1]["value"] == 120.0


@pytest.mark.asyncio
async def test_get_rates_empty(db_session) -> None:
    result = await users_data.get_rates(db_session)
    assert result == []
