"""Tests for command queue service."""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.user import UserDB
from mcp_server.models.command import CommandDB


@pytest_asyncio.fixture
async def test_user(db_session: AsyncSession) -> UserDB:
    user = UserDB(
        email="test@vizzuality.com",
        name="Test User",
        first_name="Test",
        last_name="User",
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.mark.asyncio
async def test_command_model_create(
    db_session: AsyncSession, test_user: UserDB,
) -> None:
    cmd = CommandDB(
        module="iso_docs",
        action="create_page",
        target="policies",
        payload={"title": "New Policy"},
        summary="Create page **New Policy** in Policies",
        requested_by=test_user.id,
    )
    db_session.add(cmd)
    await db_session.flush()
    await db_session.refresh(cmd)

    assert cmd.id is not None
    assert cmd.status == "pending"
    assert cmd.requested_at is not None
    assert cmd.reviewed_by is None
