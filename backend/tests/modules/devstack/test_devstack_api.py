"""Tests for devstack module API endpoints."""

from unittest.mock import AsyncMock, patch
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.user import UserDB

DEBUG_USER_ID = UUID("00000000-0000-0000-0000-000000000001")


@pytest_asyncio.fixture(autouse=True)
async def debug_user(db_session: AsyncSession) -> UserDB:
    """Create the user that DEBUG auth bypass references as created_by."""
    user = UserDB(
        id=DEBUG_USER_ID,
        email="debug@vizzuality.com",
        first_name="Debug",
        last_name="User",
        active=True,
    )
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


def _entry_payload(**overrides) -> dict:
    """Build a valid entry creation payload with sensible defaults."""
    base = {
        "name": "test-skill",
        "description": "A test skill for Claude Code",
        "type": "skill",
        "install_method": "github",
        "url": "https://github.com/Vizzuality/devstack/test-skill.md",
        "required": True,
        "origin": "internal",
        "tech": ["python"],
        "active": True,
    }
    base.update(overrides)
    return base


class TestEntryList:
    @pytest.mark.asyncio
    async def test_list_empty(self, client: AsyncClient) -> None:
        resp = await client.get("/api/devstack")
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["total"] == 0

    @pytest.mark.asyncio
    async def test_list_with_filters(self, client: AsyncClient) -> None:
        await client.post("/api/devstack", json=_entry_payload(name="my-skill", required=True))
        await client.post(
            "/api/devstack",
            json=_entry_payload(
                name="my-command",
                type="command",
                required=False,
            ),
        )

        resp_skill = await client.get("/api/devstack", params={"type": "skill"})
        assert resp_skill.status_code == 200
        assert resp_skill.json()["total"] == 1
        assert resp_skill.json()["items"][0]["name"] == "my-skill"

        resp_optional = await client.get("/api/devstack", params={"required": "false"})
        assert resp_optional.status_code == 200
        assert resp_optional.json()["total"] == 1
        assert resp_optional.json()["items"][0]["name"] == "my-command"


class TestEntryCRUD:
    @pytest.mark.asyncio
    async def test_create(self, client: AsyncClient) -> None:
        resp = await client.post("/api/devstack", json=_entry_payload())
        assert resp.status_code == 201
        data = resp.json()
        assert data["name"] == "test-skill"
        assert data["type"] == "skill"
        assert "id" in data

    @pytest.mark.asyncio
    async def test_create_duplicate_name(self, client: AsyncClient) -> None:
        await client.post("/api/devstack", json=_entry_payload())
        resp = await client.post("/api/devstack", json=_entry_payload())
        assert resp.status_code == 409

    @pytest.mark.asyncio
    async def test_get_detail(self, client: AsyncClient) -> None:
        create_resp = await client.post("/api/devstack", json=_entry_payload())
        entry_id = create_resp.json()["id"]

        resp = await client.get(f"/api/devstack/{entry_id}")
        assert resp.status_code == 200
        assert resp.json()["name"] == "test-skill"

    @pytest.mark.asyncio
    async def test_get_not_found(self, client: AsyncClient) -> None:
        resp = await client.get(f"/api/devstack/{uuid4()}")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_update(self, client: AsyncClient) -> None:
        create_resp = await client.post("/api/devstack", json=_entry_payload())
        entry_id = create_resp.json()["id"]

        resp = await client.put(
            f"/api/devstack/{entry_id}",
            json={"description": "Updated description"},
        )
        assert resp.status_code == 200
        assert resp.json()["description"] == "Updated description"

    @pytest.mark.asyncio
    async def test_delete(self, client: AsyncClient) -> None:
        create_resp = await client.post("/api/devstack", json=_entry_payload())
        entry_id = create_resp.json()["id"]

        resp = await client.delete(f"/api/devstack/{entry_id}")
        assert resp.status_code == 204

        get_resp = await client.get(f"/api/devstack/{entry_id}")
        assert get_resp.status_code == 404

    @pytest.mark.asyncio
    async def test_npm_requires_package(self, client: AsyncClient) -> None:
        payload = _entry_payload(
            name="my-npm-plugin",
            type="plugin",
            install_method="npm",
            package="@vizzuality/claude-plugin",
            url=None,
        )
        resp = await client.post("/api/devstack", json=payload)
        assert resp.status_code == 201
        data = resp.json()
        assert data["install_method"] == "npm"
        assert data["package"] == "@vizzuality/claude-plugin"


class TestGithubSha:
    @pytest.mark.asyncio
    @patch(
        "app.modules.devstack.api.entries.fetch_github_sha",
        new_callable=AsyncMock,
        return_value="a" * 40,
    )
    async def test_create_fetches_sha_for_github_entry(
        self, mock_fetch: AsyncMock, client: AsyncClient,
    ) -> None:
        resp = await client.post(
            "/api/devstack",
            json=_entry_payload(
                url="https://github.com/Vizzuality/devstack/blob/main/skills/test.md",
            ),
        )
        assert resp.status_code == 201
        assert resp.json()["github_sha"] == "a" * 40
        mock_fetch.assert_called_once()

    @pytest.mark.asyncio
    async def test_npm_entry_has_no_sha(self, client: AsyncClient) -> None:
        resp = await client.post(
            "/api/devstack",
            json=_entry_payload(
                name="npm-plugin",
                type="plugin",
                install_method="npm",
                package="@vizzuality/test-plugin",
                url=None,
            ),
        )
        assert resp.status_code == 201
        assert resp.json()["github_sha"] is None

    @pytest.mark.asyncio
    @patch(
        "app.modules.devstack.api.entries.fetch_github_sha",
        new_callable=AsyncMock,
        return_value="b" * 40,
    )
    async def test_update_refetches_sha_when_url_changes(
        self, mock_fetch: AsyncMock, client: AsyncClient,
    ) -> None:
        create_resp = await client.post(
            "/api/devstack",
            json=_entry_payload(
                url="https://github.com/Vizzuality/devstack/blob/main/skills/old.md",
            ),
        )
        entry_id = create_resp.json()["id"]
        mock_fetch.reset_mock()

        resp = await client.put(
            f"/api/devstack/{entry_id}",
            json={"url": "https://github.com/Vizzuality/devstack/blob/main/skills/new.md"},
        )
        assert resp.status_code == 200
        assert resp.json()["github_sha"] == "b" * 40
        mock_fetch.assert_called_once()


class TestSearchAndSort:
    @pytest.mark.asyncio
    async def test_search_by_name(self, client: AsyncClient) -> None:
        await client.post("/api/devstack", json=_entry_payload(name="alpha-skill"))
        await client.post("/api/devstack", json=_entry_payload(name="beta-command", type="command"))

        resp = await client.get("/api/devstack", params={"search": "alpha"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 1
        assert resp.json()["items"][0]["name"] == "alpha-skill"

    @pytest.mark.asyncio
    async def test_search_case_insensitive(self, client: AsyncClient) -> None:
        await client.post("/api/devstack", json=_entry_payload(name="MySkill"))

        resp = await client.get("/api/devstack", params={"search": "myskill"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 1

    @pytest.mark.asyncio
    async def test_sort_by_name_asc(self, client: AsyncClient) -> None:
        await client.post("/api/devstack", json=_entry_payload(name="zeta-skill"))
        await client.post("/api/devstack", json=_entry_payload(name="alpha-skill"))

        resp = await client.get("/api/devstack", params={"sort_by": "name", "sort_dir": "asc"})
        assert resp.status_code == 200
        names = [e["name"] for e in resp.json()["items"]]
        assert names == ["alpha-skill", "zeta-skill"]

    @pytest.mark.asyncio
    async def test_sort_by_name_desc(self, client: AsyncClient) -> None:
        await client.post("/api/devstack", json=_entry_payload(name="alpha-skill"))
        await client.post("/api/devstack", json=_entry_payload(name="zeta-skill"))

        resp = await client.get("/api/devstack", params={"sort_by": "name", "sort_dir": "desc"})
        assert resp.status_code == 200
        names = [e["name"] for e in resp.json()["items"]]
        assert names == ["zeta-skill", "alpha-skill"]

    @pytest.mark.asyncio
    async def test_response_includes_pagination_metadata(self, client: AsyncClient) -> None:
        await client.post("/api/devstack", json=_entry_payload())

        resp = await client.get("/api/devstack", params={"page": 1, "page_size": 10})
        assert resp.status_code == 200
        data = resp.json()
        assert data["page"] == 1
        assert data["page_size"] == 10
        assert "total" in data
        assert "items" in data

    @pytest.mark.asyncio
    async def test_featured_filter(self, client: AsyncClient) -> None:
        await client.post("/api/devstack", json=_entry_payload(name="normal-skill", featured=False))
        await client.post("/api/devstack", json=_entry_payload(name="star-skill", featured=True))

        resp = await client.get("/api/devstack", params={"featured": "true"})
        assert resp.status_code == 200
        assert resp.json()["total"] == 1
        assert resp.json()["items"][0]["name"] == "star-skill"


