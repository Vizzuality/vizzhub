"""Tests for SHA refresh service."""

from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.user import UserDB
from app.modules.devstack.models.entry import DevstackEntryDB
from app.modules.devstack.services.sha_refresh import refresh_all_shas

DEBUG_USER_ID = UUID("00000000-0000-0000-0000-000000000001")


@pytest_asyncio.fixture(autouse=True)
async def debug_user(db_session: AsyncSession) -> UserDB:
    user = UserDB(
        id=DEBUG_USER_ID,
        email="debug@vizzuality.com",
        first_name="Debug",
        last_name="User",
        active=True,
    )
    db_session.add(user)
    await db_session.commit()
    return user


@pytest_asyncio.fixture
async def github_entry(db_session: AsyncSession) -> DevstackEntryDB:
    entry = DevstackEntryDB(
        name="test-skill",
        description="A test skill",
        type="skill",
        install_method="github",
        url="https://github.com/Vizzuality/devstack/blob/main/skills/test.md",
        required=True,
        active=True,
        origin="internal",
        github_sha="old_sha_" + "x" * 32,
    )
    db_session.add(entry)
    await db_session.commit()
    await db_session.refresh(entry)
    return entry


@pytest_asyncio.fixture
async def npm_entry(db_session: AsyncSession) -> DevstackEntryDB:
    entry = DevstackEntryDB(
        name="test-plugin",
        description="A test plugin",
        type="plugin",
        install_method="npm",
        package="@vizzuality/test",
        required=False,
        active=True,
        origin="external",
    )
    db_session.add(entry)
    await db_session.commit()
    await db_session.refresh(entry)
    return entry


class TestRefreshAllShas:
    @pytest.mark.asyncio
    @patch(
        "app.modules.devstack.services.sha_refresh.fetch_github_sha",
        new_callable=AsyncMock,
        return_value="new_sha_" + "y" * 32,
    )
    async def test_updates_changed_sha(
        self, mock_fetch: AsyncMock, db_session: AsyncSession, github_entry: DevstackEntryDB,
    ) -> None:
        result = await refresh_all_shas(db_session)
        await db_session.refresh(github_entry)

        assert github_entry.github_sha == "new_sha_" + "y" * 32
        assert result["updated"] == 1
        assert result["total"] == 1

    @pytest.mark.asyncio
    @patch(
        "app.modules.devstack.services.sha_refresh.fetch_github_sha",
        new_callable=AsyncMock,
        return_value="old_sha_" + "x" * 32,
    )
    async def test_skips_unchanged_sha(
        self, mock_fetch: AsyncMock, db_session: AsyncSession, github_entry: DevstackEntryDB,
    ) -> None:
        result = await refresh_all_shas(db_session)
        assert result["unchanged"] == 1
        assert result["updated"] == 0

    @pytest.mark.asyncio
    async def test_skips_npm_entries(
        self, db_session: AsyncSession, npm_entry: DevstackEntryDB,
    ) -> None:
        result = await refresh_all_shas(db_session)
        assert result["total"] == 0

    @pytest.mark.asyncio
    @patch(
        "app.modules.devstack.services.sha_refresh.fetch_github_sha",
        new_callable=AsyncMock,
        return_value=None,
    )
    async def test_counts_failures(
        self, mock_fetch: AsyncMock, db_session: AsyncSession, github_entry: DevstackEntryDB,
    ) -> None:
        result = await refresh_all_shas(db_session)
        assert result["failed"] == 1
        assert result["updated"] == 0
