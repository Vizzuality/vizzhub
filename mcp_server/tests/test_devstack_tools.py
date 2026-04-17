"""Tests for MCP DevStack tools."""

from __future__ import annotations

import json
from uuid import UUID

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.user import UserDB
from app.modules.devstack.models.entry import DevstackEntryDB
from app.modules.devstack.models.user_pref import DevstackUserPrefDB
from mcp_server.data.base import McpUserContext, override_mcp_user, override_session
from mcp_server.tools.devstack import devstack_get_catalog, devstack_update_sync_status

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
async def required_entry(db_session: AsyncSession) -> DevstackEntryDB:
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
async def optional_entry(db_session: AsyncSession) -> DevstackEntryDB:
    entry = DevstackEntryDB(
        name="optional-plugin",
        description="Optional MCP plugin",
        type="plugin",
        install_method="npm",
        package="@vizzuality/mcp-plugin",
        required=False,
        active=True,
        origin="external",
        tech=[],
    )
    db_session.add(entry)
    await db_session.commit()
    await db_session.refresh(entry)
    return entry


class TestGetCatalog:
    @pytest.mark.asyncio
    async def test_returns_required_entries(
        self, db_session: AsyncSession, required_entry: DevstackEntryDB,
    ) -> None:
        async with override_session(db_session):
            async with override_mcp_user(USER_CTX):
                result = await devstack_get_catalog()

        data = json.loads(result)
        assert isinstance(data, list)
        assert len(data) == 1
        assert data[0]["name"] == "org-skill"

    @pytest.mark.asyncio
    async def test_excludes_optional_not_opted_in(
        self,
        db_session: AsyncSession,
        required_entry: DevstackEntryDB,
        optional_entry: DevstackEntryDB,
    ) -> None:
        async with override_session(db_session):
            async with override_mcp_user(USER_CTX):
                result = await devstack_get_catalog()

        data = json.loads(result)
        names = [item["name"] for item in data]
        assert "org-skill" in names
        assert "optional-plugin" not in names

    @pytest.mark.asyncio
    async def test_includes_opted_in_optional(
        self,
        db_session: AsyncSession,
        required_entry: DevstackEntryDB,
        optional_entry: DevstackEntryDB,
    ) -> None:
        pref = DevstackUserPrefDB(
            user_id=TEST_USER_ID,
            entry_id=optional_entry.id,
            enabled=True,
        )
        db_session.add(pref)
        await db_session.commit()

        async with override_session(db_session):
            async with override_mcp_user(USER_CTX):
                result = await devstack_get_catalog()

        data = json.loads(result)
        names = [item["name"] for item in data]
        assert "org-skill" in names
        assert "optional-plugin" in names
        assert len(data) == 2


class TestUpdateSyncStatus:
    @pytest.mark.asyncio
    async def test_update_creates_pref_if_missing(
        self, db_session: AsyncSession, required_entry: DevstackEntryDB,
    ) -> None:
        async with override_session(db_session):
            async with override_mcp_user(USER_CTX):
                result = await devstack_update_sync_status(
                    entry_name="org-skill",
                    sha="abc1234",
                )

        data = json.loads(result)
        assert data["status"] == "ok"
        assert data["entry_name"] == "org-skill"
        assert data["sha"] == "abc1234"

    @pytest.mark.asyncio
    async def test_update_nonexistent_entry(
        self, db_session: AsyncSession,
    ) -> None:
        async with override_session(db_session):
            async with override_mcp_user(USER_CTX):
                result = await devstack_update_sync_status(
                    entry_name="no-such-entry",
                    sha="abc1234",
                )

        data = json.loads(result)
        assert "error" in data
        assert "no-such-entry" in data["error"]
