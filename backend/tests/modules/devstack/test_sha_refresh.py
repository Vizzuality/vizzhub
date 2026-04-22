"""Tests for source refresh service (github SHAs + npm versions)."""

from unittest.mock import AsyncMock, patch
from uuid import UUID

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.user import UserDB
from app.modules.devstack.models.entry import DevstackEntryDB
from app.modules.devstack.services.sha_refresh import refresh_all_sources

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
        name="test-npm",
        description="A test npm package",
        type="plugin",
        install_method="npm",
        package="react",
        required=False,
        active=True,
        origin="external",
        latest_package_version=None,
    )
    db_session.add(entry)
    await db_session.commit()
    await db_session.refresh(entry)
    return entry


@pytest_asyncio.fixture
async def claude_plugin_entry(db_session: AsyncSession) -> DevstackEntryDB:
    entry = DevstackEntryDB(
        name="test-claude-plugin",
        description="A test claude plugin",
        type="plugin",
        install_method="claude_plugin",
        package="superpowers@claude-plugins-official",
        required=False,
        active=True,
        origin="external",
    )
    db_session.add(entry)
    await db_session.commit()
    await db_session.refresh(entry)
    return entry


class TestRefreshGithub:
    @pytest.mark.asyncio
    @patch(
        "app.modules.devstack.services.sha_refresh.fetch_github_content",
        new_callable=AsyncMock,
        return_value=None,
    )
    @patch(
        "app.modules.devstack.services.sha_refresh.fetch_github_sha",
        new_callable=AsyncMock,
        return_value="new_sha_" + "y" * 32,
    )
    async def test_updates_changed_sha(
        self,
        mock_fetch: AsyncMock,
        mock_content: AsyncMock,
        db_session: AsyncSession,
        github_entry: DevstackEntryDB,
    ) -> None:
        result = await refresh_all_sources(db_session)
        await db_session.refresh(github_entry)

        assert github_entry.github_sha == "new_sha_" + "y" * 32
        assert result["updated"] == 1

    @pytest.mark.asyncio
    @patch(
        "app.modules.devstack.services.sha_refresh.fetch_github_sha",
        new_callable=AsyncMock,
        return_value="old_sha_" + "x" * 32,
    )
    async def test_skips_unchanged_sha(
        self, mock_fetch: AsyncMock, db_session: AsyncSession, github_entry: DevstackEntryDB,
    ) -> None:
        result = await refresh_all_sources(db_session)
        assert result["unchanged"] == 1
        assert result["updated"] == 0

    @pytest.mark.asyncio
    @patch(
        "app.modules.devstack.services.sha_refresh.fetch_github_sha",
        new_callable=AsyncMock,
        return_value=None,
    )
    async def test_counts_github_failures(
        self, mock_fetch: AsyncMock, db_session: AsyncSession, github_entry: DevstackEntryDB,
    ) -> None:
        result = await refresh_all_sources(db_session)
        assert result["failed"] == 1
        assert result["updated"] == 0

    @pytest.mark.asyncio
    @patch(
        "app.modules.devstack.services.sha_refresh.fetch_github_content",
        new_callable=AsyncMock,
        return_value=(
            "---\n"
            "name: test-skill\n"
            "description: Refreshed description from frontmatter\n"
            "devstack_sha: abc\n"
            "---\n\n# Body\n"
        ),
    )
    @patch(
        "app.modules.devstack.services.sha_refresh.fetch_github_sha",
        new_callable=AsyncMock,
        return_value="new_sha_" + "y" * 32,
    )
    async def test_refreshes_description_from_frontmatter_on_sha_change(
        self,
        mock_fetch: AsyncMock,
        mock_content: AsyncMock,
        db_session: AsyncSession,
        github_entry: DevstackEntryDB,
    ) -> None:
        await refresh_all_sources(db_session)
        await db_session.refresh(github_entry)

        assert github_entry.description == "Refreshed description from frontmatter"
        assert github_entry.github_sha == "new_sha_" + "y" * 32

    @pytest.mark.asyncio
    @patch(
        "app.modules.devstack.services.sha_refresh.fetch_github_content",
        new_callable=AsyncMock,
    )
    @patch(
        "app.modules.devstack.services.sha_refresh.fetch_github_sha",
        new_callable=AsyncMock,
        return_value="old_sha_" + "x" * 32,
    )
    async def test_skips_content_fetch_when_sha_unchanged(
        self,
        mock_fetch: AsyncMock,
        mock_content: AsyncMock,
        db_session: AsyncSession,
        github_entry: DevstackEntryDB,
    ) -> None:
        await refresh_all_sources(db_session)
        assert mock_content.await_count == 0


class TestRefreshNpm:
    @pytest.mark.asyncio
    @patch(
        "app.modules.devstack.services.sha_refresh.fetch_npm_advisories",
        new_callable=AsyncMock,
        return_value=None,
    )
    @patch(
        "app.modules.devstack.services.sha_refresh.fetch_npm_package_info",
        new_callable=AsyncMock,
        return_value={"version": "18.3.1", "deprecation_message": None},
    )
    async def test_updates_changed_version(
        self,
        mock_info: AsyncMock,
        mock_advisories: AsyncMock,
        db_session: AsyncSession,
        npm_entry: DevstackEntryDB,
    ) -> None:
        result = await refresh_all_sources(db_session)
        await db_session.refresh(npm_entry)

        assert npm_entry.latest_package_version == "18.3.1"
        assert result["updated"] == 1

    @pytest.mark.asyncio
    @patch(
        "app.modules.devstack.services.sha_refresh.fetch_npm_advisories",
        new_callable=AsyncMock,
        return_value=None,
    )
    @patch(
        "app.modules.devstack.services.sha_refresh.fetch_npm_package_info",
        new_callable=AsyncMock,
        return_value={"version": "18.3.1", "deprecation_message": None},
    )
    async def test_skips_unchanged_version(
        self,
        mock_info: AsyncMock,
        mock_advisories: AsyncMock,
        db_session: AsyncSession,
        npm_entry: DevstackEntryDB,
    ) -> None:
        npm_entry.latest_package_version = "18.3.1"
        db_session.add(npm_entry)
        await db_session.commit()

        result = await refresh_all_sources(db_session)
        assert result["unchanged"] == 1
        assert result["updated"] == 0

    @pytest.mark.asyncio
    @patch(
        "app.modules.devstack.services.sha_refresh.fetch_npm_package_info",
        new_callable=AsyncMock,
        return_value=None,
    )
    async def test_counts_npm_failures(
        self, mock_info: AsyncMock, db_session: AsyncSession, npm_entry: DevstackEntryDB,
    ) -> None:
        result = await refresh_all_sources(db_session)
        assert result["failed"] == 1

    @pytest.mark.asyncio
    @patch(
        "app.modules.devstack.services.sha_refresh.fetch_npm_advisories",
        new_callable=AsyncMock,
        return_value={
            "critical": 1, "high": 0, "moderate": 0, "low": 0,
            "advisories": [
                {"id": "GHSA-a", "severity": "critical", "title": "t", "url": "u"}
            ],
        },
    )
    @patch(
        "app.modules.devstack.services.sha_refresh.fetch_npm_package_info",
        new_callable=AsyncMock,
        return_value={"version": "4.17.21", "deprecation_message": "use foo"},
    )
    async def test_updates_deprecation_and_vulnerabilities(
        self,
        mock_info: AsyncMock,
        mock_advisories: AsyncMock,
        db_session: AsyncSession,
        npm_entry: DevstackEntryDB,
    ) -> None:
        result = await refresh_all_sources(db_session)
        await db_session.refresh(npm_entry)

        assert result["updated"] >= 1
        assert npm_entry.latest_package_version == "4.17.21"
        assert npm_entry.deprecated is True
        assert npm_entry.deprecation_message == "use foo"
        assert npm_entry.vulnerabilities["critical"] == 1
        assert len(npm_entry.vulnerabilities["advisories"]) == 1
        assert npm_entry.vulnerabilities_checked_at is not None

    @pytest.mark.asyncio
    @patch(
        "app.modules.devstack.services.sha_refresh.fetch_npm_advisories",
        new_callable=AsyncMock,
        return_value={
            "critical": 0, "high": 0, "moderate": 0, "low": 0, "advisories": []
        },
    )
    @patch(
        "app.modules.devstack.services.sha_refresh.fetch_npm_package_info",
        new_callable=AsyncMock,
        return_value={"version": "1.0.1", "deprecation_message": None},
    )
    async def test_clears_deprecation_when_unset(
        self,
        mock_info: AsyncMock,
        mock_advisories: AsyncMock,
        db_session: AsyncSession,
        npm_entry: DevstackEntryDB,
    ) -> None:
        # Pre-mark the entry as deprecated to verify the cron clears it
        npm_entry.deprecated = True
        npm_entry.deprecation_message = "old"
        db_session.add(npm_entry)
        await db_session.commit()

        await refresh_all_sources(db_session)
        await db_session.refresh(npm_entry)

        assert npm_entry.deprecated is False
        assert npm_entry.deprecation_message is None


    @pytest.mark.asyncio
    @patch(
        "app.modules.devstack.services.sha_refresh.fetch_npm_advisories",
        new_callable=AsyncMock,
        return_value={
            "critical": 0, "high": 0, "moderate": 0, "low": 0, "advisories": []
        },
    )
    @patch(
        "app.modules.devstack.services.sha_refresh.fetch_npm_package_info",
        new_callable=AsyncMock,
        return_value={"version": "18.3.1", "deprecation_message": None},
    )
    async def test_unchanged_advisories_do_not_count_as_update(
        self,
        mock_info: AsyncMock,
        mock_advisories: AsyncMock,
        db_session: AsyncSession,
        npm_entry: DevstackEntryDB,
    ) -> None:
        """If version, deprecation AND advisories are all unchanged, entry is 'unchanged'."""
        # Pre-load the npm entry with matching state so only checked_at changes
        npm_entry.latest_package_version = "18.3.1"
        npm_entry.vulnerabilities = {
            "critical": 0, "high": 0, "moderate": 0, "low": 0, "advisories": []
        }
        db_session.add(npm_entry)
        await db_session.commit()

        result = await refresh_all_sources(db_session)

        assert result["updated"] == 0
        assert result["unchanged"] == 1


class TestClaudePluginSkipped:
    @pytest.mark.asyncio
    async def test_claude_plugin_not_counted(
        self, db_session: AsyncSession, claude_plugin_entry: DevstackEntryDB,
    ) -> None:
        result = await refresh_all_sources(db_session)
        assert result["total"] == 0
