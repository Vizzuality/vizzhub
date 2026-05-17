"""Tests for ISO docs visibility-based access control.

Verifies that:
- Regular users can only see nodes under USER_VISIBLE_ROOT_SLUGS (policies, procedures)
- ISO docs editors can access all documents
- Tree, pages, versions, metadata, and search endpoints all respect visibility
"""

from collections.abc import AsyncGenerator
from uuid import UUID

import pytest
import pytest_asyncio
from httpx import AsyncClient
from httpx._transports.asgi import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api.deps import get_db
from app.core.auth import TokenData, get_current_user
from app.main import app

EDITOR_USER_ID = UUID("00000000-0000-0000-0000-000000000001")
REGULAR_USER_ID = UUID("00000000-0000-0000-0000-000000000002")

EDITOR_TOKEN = TokenData(
    user_id=str(EDITOR_USER_ID),
    email="editor@test.com",
    roles=["user", "iso_docs_editor"],
    permissions=["iso_docs:edit"],
)

REGULAR_TOKEN = TokenData(
    user_id=str(REGULAR_USER_ID),
    email="user@test.com",
    roles=["user"],
    permissions=["scorecard:view", "tracker:view"],
)


def _override_user(token: TokenData):
    async def _get_user() -> TokenData:
        return token

    return _get_user


@pytest_asyncio.fixture
async def _setup_db(db_session: AsyncSession):
    async def override_get_db() -> AsyncGenerator[AsyncSession]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_data(_setup_db) -> dict:
    """Create test tree: policies group with a page, and a restricted root-level page."""
    app.dependency_overrides[get_current_user] = _override_user(EDITOR_TOKEN)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        # Create "Policies" group (slug = "policies" -> visible to regular users)
        r_group = await c.post("/api/iso-docs/nodes", json={"title": "Policies", "type": "group"})
        policies_group = r_group.json()

        # Create a page under Policies
        r1 = await c.post(
            "/api/iso-docs/nodes",
            json={
                "title": "Public Policy",
                "type": "page",
                "parent_id": policies_group["id"],
            },
        )
        visible_page = r1.json()
        await c.put(
            f"/api/iso-docs/pages/{visible_page['id']}",
            json={"content": "# Public Policy\nVisible to all.", "expected_version": 0},
        )
        await c.put(
            f"/api/iso-docs/pages/{visible_page['id']}/metadata",
            json={"code": "PUB01"},
        )

        # Create a root-level page (NOT under policies/procedures -> hidden from regular users)
        r2 = await c.post("/api/iso-docs/nodes", json={"title": "Secret Record", "type": "page"})
        hidden_page = r2.json()
        await c.put(
            f"/api/iso-docs/pages/{hidden_page['id']}",
            json={"content": "# Secret Record\nRestricted.", "expected_version": 0},
        )
        await c.put(
            f"/api/iso-docs/pages/{hidden_page['id']}/metadata",
            json={"code": "SEC01"},
        )

    return {
        "policies_group": policies_group,
        "visible": visible_page,
        "hidden": hidden_page,
    }


async def _client_as(token: TokenData) -> AsyncGenerator[AsyncClient]:
    app.dependency_overrides[get_current_user] = _override_user(token)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


def _collect_ids(tree: list[dict]) -> set[str]:
    """Recursively collect all node IDs from a tree response."""
    ids: set[str] = set()
    for node in tree:
        ids.add(node["id"])
        ids.update(_collect_ids(node.get("children", [])))
    return ids


class TestTreeFiltering:
    @pytest.mark.asyncio
    async def test_editor_sees_all_nodes(self, test_data: dict):
        async for c in _client_as(EDITOR_TOKEN):
            resp = await c.get("/api/iso-docs/tree")
            assert resp.status_code == 200
            ids = _collect_ids(resp.json())
            assert test_data["visible"]["id"] in ids
            assert test_data["hidden"]["id"] in ids

    @pytest.mark.asyncio
    async def test_regular_user_sees_only_visible_roots(self, test_data: dict):
        async for c in _client_as(REGULAR_TOKEN):
            resp = await c.get("/api/iso-docs/tree")
            assert resp.status_code == 200
            ids = _collect_ids(resp.json())
            assert test_data["policies_group"]["id"] in ids
            assert test_data["visible"]["id"] in ids
            assert test_data["hidden"]["id"] not in ids


class TestPageAccess:
    @pytest.mark.asyncio
    async def test_regular_user_can_read_visible_page(self, test_data: dict):
        async for c in _client_as(REGULAR_TOKEN):
            resp = await c.get(f"/api/iso-docs/pages/{test_data['visible']['id']}")
            assert resp.status_code == 200
            assert resp.json()["title"] == "Public Policy"

    @pytest.mark.asyncio
    async def test_regular_user_blocked_from_hidden_page(self, test_data: dict):
        async for c in _client_as(REGULAR_TOKEN):
            resp = await c.get(f"/api/iso-docs/pages/{test_data['hidden']['id']}")
            assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_editor_can_read_hidden_page(self, test_data: dict):
        async for c in _client_as(EDITOR_TOKEN):
            resp = await c.get(f"/api/iso-docs/pages/{test_data['hidden']['id']}")
            assert resp.status_code == 200


class TestVersionAccess:
    @pytest.mark.asyncio
    async def test_regular_user_blocked_from_hidden_versions(self, test_data: dict):
        async for c in _client_as(REGULAR_TOKEN):
            resp = await c.get(f"/api/iso-docs/pages/{test_data['hidden']['id']}/versions")
            assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_regular_user_blocked_from_hidden_version_detail(self, test_data: dict):
        async for c in _client_as(REGULAR_TOKEN):
            resp = await c.get(f"/api/iso-docs/pages/{test_data['hidden']['id']}/versions/1")
            assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_editor_can_list_hidden_versions(self, test_data: dict):
        async for c in _client_as(EDITOR_TOKEN):
            resp = await c.get(f"/api/iso-docs/pages/{test_data['hidden']['id']}/versions")
            assert resp.status_code == 200


class TestMetadataAccess:
    @pytest.mark.asyncio
    async def test_regular_user_blocked_from_hidden_metadata(self, test_data: dict):
        async for c in _client_as(REGULAR_TOKEN):
            resp = await c.get(f"/api/iso-docs/pages/{test_data['hidden']['id']}/metadata")
            assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_regular_user_can_read_visible_metadata(self, test_data: dict):
        async for c in _client_as(REGULAR_TOKEN):
            resp = await c.get(f"/api/iso-docs/pages/{test_data['visible']['id']}/metadata")
            assert resp.status_code == 200

    @pytest.mark.asyncio
    async def test_metadata_search_excludes_hidden_for_regular_user(self, test_data: dict):
        async for c in _client_as(REGULAR_TOKEN):
            resp = await c.get("/api/iso-docs/metadata/search")
            assert resp.status_code == 200
            codes = {r["code"] for r in resp.json()}
            assert "PUB01" in codes
            assert "SEC01" not in codes

    @pytest.mark.asyncio
    async def test_metadata_search_includes_all_for_editor(self, test_data: dict):
        async for c in _client_as(EDITOR_TOKEN):
            resp = await c.get("/api/iso-docs/metadata/search")
            assert resp.status_code == 200
            codes = {r["code"] for r in resp.json()}
            assert "PUB01" in codes
            assert "SEC01" in codes


class TestSearchFiltering:
    @pytest.mark.asyncio
    async def test_text_search_excludes_hidden_for_regular_user(self, test_data: dict):
        async for c in _client_as(REGULAR_TOKEN):
            resp = await c.get("/api/iso-docs/pages/search?q=Policy")
            assert resp.status_code == 200
            titles = {r["title"] for r in resp.json()}
            assert "Public Policy" in titles
            assert "Secret Record" not in titles

    @pytest.mark.asyncio
    async def test_text_search_includes_all_for_editor(self, test_data: dict):
        async for c in _client_as(EDITOR_TOKEN):
            resp = await c.get("/api/iso-docs/pages/search?q=Policy")
            assert resp.status_code == 200
            titles = {r["title"] for r in resp.json()}
            assert "Public Policy" in titles
