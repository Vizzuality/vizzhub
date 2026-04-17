"""Tests for MCP DevStack tools."""

from __future__ import annotations

import json
from uuid import UUID

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.user import UserDB
from app.modules.devstack.models.entry import DevstackEntryDB
from mcp_server.data.base import McpUserContext, override_mcp_user, override_session
from mcp_server.tools.devstack import devstack_get_catalog

TEST_USER_ID = UUID("00000000-0000-0000-0000-000000000099")

USER_CTX = McpUserContext(
    user_id=str(TEST_USER_ID),
    email="dev@vizzuality.com",
    roles=["user"],
    permissions=["devstack:view"],
)


@pytest_asyncio.fixture(autouse=True)
async def test_user(db_session: AsyncSession) -> UserDB:
    user = UserDB(id=TEST_USER_ID, email="dev@vizzuality.com", name="Dev User")
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest_asyncio.fixture
async def active_entry(db_session: AsyncSession) -> DevstackEntryDB:
    entry = DevstackEntryDB(
        name="org-skill",
        description="Required org-wide Claude Code skill",
        type="skill",
        install_method="github",
        url="https://github.com/vizzuality/skills",
        required=True,
        active=True,
        origin="internal",
        tech=["claude-code"],
    )
    db_session.add(entry)
    await db_session.commit()
    await db_session.refresh(entry)
    return entry


@pytest_asyncio.fixture
async def inactive_entry(db_session: AsyncSession) -> DevstackEntryDB:
    entry = DevstackEntryDB(
        name="deprecated-plugin",
        description="Old plugin no longer in use",
        type="plugin",
        install_method="npm",
        package="@vizzuality/old-plugin",
        required=False,
        active=False,
        origin="external",
        tech=[],
    )
    db_session.add(entry)
    await db_session.commit()
    await db_session.refresh(entry)
    return entry


class TestGetCatalog:
    @pytest.mark.asyncio
    async def test_returns_active_entries(
        self, db_session: AsyncSession, active_entry: DevstackEntryDB,
    ) -> None:
        async with override_session(db_session):
            async with override_mcp_user(USER_CTX):
                result = await devstack_get_catalog()

        data = json.loads(result)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["name"] == "org-skill"

    @pytest.mark.asyncio
    async def test_excludes_inactive_entries(
        self,
        db_session: AsyncSession,
        active_entry: DevstackEntryDB,
        inactive_entry: DevstackEntryDB,
    ) -> None:
        async with override_session(db_session):
            async with override_mcp_user(USER_CTX):
                result = await devstack_get_catalog()

        data = json.loads(result)
        names = [item["name"] for item in data]
        assert "org-skill" in names
        assert "deprecated-plugin" not in names
        assert len(data) == 1
