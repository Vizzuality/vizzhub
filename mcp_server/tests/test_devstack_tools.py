"""Tests for MCP DevStack tools."""

from __future__ import annotations

import json
from unittest.mock import patch
from uuid import UUID

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.user import UserDB
from app.modules.devstack.models.entry import DevstackEntryDB
from mcp_server.data.base import McpUserContext, override_mcp_user, override_session
from mcp_server.tools.devstack import (
    devstack_discover,
    devstack_get_catalog,
    devstack_get_installable,
    devstack_get_tech_radar,
)

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
        github_sha="a" * 40,
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


@pytest_asyncio.fixture
async def discover_entries(db_session: AsyncSession) -> list[DevstackEntryDB]:
    entries = [
        DevstackEntryDB(
            name="zeta-agent",
            description="Zeta agent",
            type="agent",
            install_method="github",
            url="https://github.com/x/y",
            required=False,
            active=True,
            origin="internal",
            tech=["python"],
            featured=True,
        ),
        DevstackEntryDB(
            name="alpha-skill",
            description="Alpha skill (required)",
            type="skill",
            install_method="github",
            url="https://github.com/x/y",
            required=True,
            active=True,
            origin="internal",
            tech=["python", "testing"],
        ),
        DevstackEntryDB(
            name="beta-skill",
            description="Beta skill",
            type="skill",
            install_method="github",
            url="https://github.com/x/y",
            required=False,
            active=True,
            origin="internal",
            tech=["react"],
        ),
        DevstackEntryDB(
            name="gamma-command",
            description="Gamma command",
            type="command",
            install_method="github",
            url="https://github.com/x/y",
            required=False,
            active=True,
            origin="internal",
            tech=[],
        ),
    ]
    for entry in entries:
        db_session.add(entry)
    await db_session.commit()
    for entry in entries:
        await db_session.refresh(entry)
    return entries


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
        assert data[0]["github_sha"] == "a" * 40
        assert data[0]["required"] is True

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


class TestDiscover:
    @pytest.mark.asyncio
    async def test_returns_only_projected_fields(
        self,
        db_session: AsyncSession,
        active_entry: DevstackEntryDB,
    ) -> None:
        async with override_session(db_session):
            async with override_mcp_user(USER_CTX):
                result = await devstack_discover()

        data = json.loads(result)
        assert len(data) == 1
        assert set(data[0].keys()) == {"name", "type", "description"}

    @pytest.mark.asyncio
    async def test_orders_featured_then_required_then_name(
        self,
        db_session: AsyncSession,
        discover_entries: list[DevstackEntryDB],
    ) -> None:
        async with override_session(db_session):
            async with override_mcp_user(USER_CTX):
                result = await devstack_discover()

        names = [item["name"] for item in json.loads(result)]
        assert names == ["zeta-agent", "alpha-skill", "beta-skill", "gamma-command"]

    @pytest.mark.asyncio
    async def test_filters_by_type(
        self,
        db_session: AsyncSession,
        discover_entries: list[DevstackEntryDB],
    ) -> None:
        async with override_session(db_session):
            async with override_mcp_user(USER_CTX):
                result = await devstack_discover(type="skill")

        names = [item["name"] for item in json.loads(result)]
        assert names == ["alpha-skill", "beta-skill"]

    @pytest.mark.asyncio
    async def test_filters_by_tech_any_match(
        self,
        db_session: AsyncSession,
        discover_entries: list[DevstackEntryDB],
    ) -> None:
        async with override_session(db_session):
            async with override_mcp_user(USER_CTX):
                result = await devstack_discover(tech=["python"])

        names = sorted(item["name"] for item in json.loads(result))
        assert names == ["alpha-skill", "zeta-agent"]

    @pytest.mark.asyncio
    async def test_filters_featured_only(
        self,
        db_session: AsyncSession,
        discover_entries: list[DevstackEntryDB],
    ) -> None:
        async with override_session(db_session):
            async with override_mcp_user(USER_CTX):
                result = await devstack_discover(featured_only=True)

        names = [item["name"] for item in json.loads(result)]
        assert names == ["zeta-agent"]

    @pytest.mark.asyncio
    async def test_excludes_inactive_entries(
        self,
        db_session: AsyncSession,
        active_entry: DevstackEntryDB,
        inactive_entry: DevstackEntryDB,
    ) -> None:
        async with override_session(db_session):
            async with override_mcp_user(USER_CTX):
                result = await devstack_discover()

        names = [item["name"] for item in json.loads(result)]
        assert "deprecated-plugin" not in names


class TestGetTechRadar:
    @pytest.mark.asyncio
    async def test_returns_content_from_github(
        self, db_session: AsyncSession,
    ) -> None:
        fake_md = "# Adopt\n- FastAPI\n"
        with (
            patch(
                "mcp_server.data.devstack.IntegrationTokenService.get_token",
                return_value="ghp_fake",
            ),
            patch(
                "mcp_server.data.devstack.fetch_github_content",
                return_value=fake_md,
            ) as mock_fetch,
        ):
            async with override_session(db_session):
                async with override_mcp_user(USER_CTX):
                    result = await devstack_get_tech_radar(file="development")

        assert result == fake_md
        called_url = mock_fetch.call_args.args[0]
        assert called_url.endswith("/decisions/tech-radar/development.md")
        assert mock_fetch.call_args.args[1] == "ghp_fake"

    @pytest.mark.asyncio
    async def test_returns_error_json_when_fetch_fails(
        self, db_session: AsyncSession,
    ) -> None:
        with (
            patch(
                "mcp_server.data.devstack.IntegrationTokenService.get_token",
                return_value=None,
            ),
            patch(
                "mcp_server.data.devstack.fetch_github_content",
                return_value=None,
            ),
        ):
            async with override_session(db_session):
                async with override_mcp_user(USER_CTX):
                    result = await devstack_get_tech_radar(file="devops")

        data = json.loads(result)
        assert "error" in data
        assert "devops.md" in data["error"]


@pytest_asyncio.fixture
async def skill_entry(db_session: AsyncSession) -> DevstackEntryDB:
    entry = DevstackEntryDB(
        name="finalize",
        description="Finalize skill",
        type="skill",
        install_method="github",
        url="https://github.com/vizzuality/claude-code-standards/blob/main/skills/finalize/SKILL.md",
        required=True,
        active=True,
        origin="internal",
        tech=["claude-code"],
        github_sha="a" * 40,
    )
    db_session.add(entry)
    await db_session.commit()
    await db_session.refresh(entry)
    return entry


class TestGetInstallable:
    @pytest.mark.asyncio
    async def test_injects_sha_into_existing_frontmatter(
        self, db_session: AsyncSession, skill_entry: DevstackEntryDB,
    ) -> None:
        source = "---\nname: finalize\ndescription: Wrap up\n---\n\nBody text.\n"
        with (
            patch(
                "mcp_server.data.devstack.IntegrationTokenService.get_token",
                return_value="ghp_fake",
            ),
            patch(
                "mcp_server.data.devstack.fetch_github_content",
                return_value=source,
            ),
        ):
            async with override_session(db_session):
                async with override_mcp_user(USER_CTX):
                    result = await devstack_get_installable(name="finalize")

        data = json.loads(result)
        assert data["target_path"] == "~/.claude/skills/finalize/SKILL.md"
        assert f"devstack_sha: {'a' * 40}" in data["content"]
        assert "name: finalize" in data["content"]
        assert "Body text." in data["content"]

    @pytest.mark.asyncio
    async def test_replaces_existing_sha_line(
        self, db_session: AsyncSession, skill_entry: DevstackEntryDB,
    ) -> None:
        source = (
            "---\nname: finalize\ndevstack_sha: oldsha\ndescription: x\n---\n\nBody.\n"
        )
        with (
            patch(
                "mcp_server.data.devstack.IntegrationTokenService.get_token",
                return_value="ghp_fake",
            ),
            patch(
                "mcp_server.data.devstack.fetch_github_content",
                return_value=source,
            ),
        ):
            async with override_session(db_session):
                async with override_mcp_user(USER_CTX):
                    result = await devstack_get_installable(name="finalize")

        content = json.loads(result)["content"]
        assert "devstack_sha: oldsha" not in content
        assert f"devstack_sha: {'a' * 40}" in content
        # Ensure sha isn't duplicated
        assert content.count("devstack_sha:") == 1

    @pytest.mark.asyncio
    async def test_prepends_frontmatter_when_missing(
        self, db_session: AsyncSession, skill_entry: DevstackEntryDB,
    ) -> None:
        source = "# Just a heading\n\nBody.\n"
        with (
            patch(
                "mcp_server.data.devstack.IntegrationTokenService.get_token",
                return_value="ghp_fake",
            ),
            patch(
                "mcp_server.data.devstack.fetch_github_content",
                return_value=source,
            ),
        ):
            async with override_session(db_session):
                async with override_mcp_user(USER_CTX):
                    result = await devstack_get_installable(name="finalize")

        content = json.loads(result)["content"]
        assert content.startswith(f"---\ndevstack_sha: {'a' * 40}\n---\n")
        assert "# Just a heading" in content

    @pytest.mark.asyncio
    async def test_target_path_per_type(
        self, db_session: AsyncSession,
    ) -> None:
        entries = [
            DevstackEntryDB(
                name="my-cmd", description="x", type="command",
                install_method="github", url="https://github.com/a/b/blob/main/c.md",
                active=True, origin="internal", tech=[], github_sha="b" * 40,
            ),
            DevstackEntryDB(
                name="my-agent", description="x", type="agent",
                install_method="github", url="https://github.com/a/b/blob/main/c.md",
                active=True, origin="internal", tech=[], github_sha="c" * 40,
            ),
        ]
        for entry in entries:
            db_session.add(entry)
        await db_session.commit()

        with (
            patch(
                "mcp_server.data.devstack.IntegrationTokenService.get_token",
                return_value=None,
            ),
            patch(
                "mcp_server.data.devstack.fetch_github_content",
                return_value="body\n",
            ),
        ):
            async with override_session(db_session):
                async with override_mcp_user(USER_CTX):
                    cmd = json.loads(await devstack_get_installable(name="my-cmd"))
                    agent = json.loads(await devstack_get_installable(name="my-agent"))

        assert cmd["target_path"] == "~/.claude/commands/my-cmd.md"
        assert agent["target_path"] == "~/.claude/agents/my-agent.md"

    @pytest.mark.asyncio
    async def test_error_not_found(
        self, db_session: AsyncSession,
    ) -> None:
        async with override_session(db_session):
            async with override_mcp_user(USER_CTX):
                result = await devstack_get_installable(name="does-not-exist")

        data = json.loads(result)
        assert data["code"] == "NOT_FOUND"

    @pytest.mark.asyncio
    async def test_error_inactive_treated_as_not_found(
        self,
        db_session: AsyncSession,
        inactive_entry: DevstackEntryDB,
    ) -> None:
        async with override_session(db_session):
            async with override_mcp_user(USER_CTX):
                result = await devstack_get_installable(name=inactive_entry.name)

        data = json.loads(result)
        assert data["code"] == "NOT_FOUND"

    @pytest.mark.asyncio
    async def test_error_unsupported_type(
        self, db_session: AsyncSession,
    ) -> None:
        entry = DevstackEntryDB(
            name="my-plugin",
            description="Plugin",
            type="plugin",
            install_method="npm",
            package="@vizzuality/plugin",
            active=True,
            origin="internal",
            tech=[],
        )
        db_session.add(entry)
        await db_session.commit()

        async with override_session(db_session):
            async with override_mcp_user(USER_CTX):
                result = await devstack_get_installable(name="my-plugin")

        data = json.loads(result)
        assert data["code"] == "UNSUPPORTED_TYPE"

    @pytest.mark.asyncio
    async def test_error_no_sha(
        self, db_session: AsyncSession,
    ) -> None:
        entry = DevstackEntryDB(
            name="no-sha-skill",
            description="x",
            type="skill",
            install_method="github",
            url="https://github.com/a/b/blob/main/c.md",
            active=True,
            origin="internal",
            tech=[],
            github_sha=None,
        )
        db_session.add(entry)
        await db_session.commit()

        async with override_session(db_session):
            async with override_mcp_user(USER_CTX):
                result = await devstack_get_installable(name="no-sha-skill")

        data = json.loads(result)
        assert data["code"] == "NO_SHA"

    @pytest.mark.asyncio
    async def test_error_fetch_failed(
        self, db_session: AsyncSession, skill_entry: DevstackEntryDB,
    ) -> None:
        with (
            patch(
                "mcp_server.data.devstack.IntegrationTokenService.get_token",
                return_value="ghp_fake",
            ),
            patch(
                "mcp_server.data.devstack.fetch_github_content",
                return_value=None,
            ),
        ):
            async with override_session(db_session):
                async with override_mcp_user(USER_CTX):
                    result = await devstack_get_installable(name="finalize")

        data = json.loads(result)
        assert data["code"] == "FETCH_FAILED"
