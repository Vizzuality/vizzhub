"""Tests for ISO docs classification-based access control.

Verifies that:
- Regular users can access internal_use documents but not confidential ones
- ISO docs editors can access all documents including confidential
- Tree, pages, versions, metadata, and search endpoints all respect classification
"""

from collections.abc import AsyncGenerator
from uuid import UUID

import pytest
import pytest_asyncio
from httpx import AsyncClient
from httpx._transports.asgi import ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TokenData, get_current_user
from app.core.api.deps import get_db
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
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def test_data(_setup_db) -> dict:
    """Create test pages as editor, return node dicts."""
    app.dependency_overrides[get_current_user] = _override_user(EDITOR_TOKEN)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        r1 = await c.post("/api/iso-docs/nodes", json={"title": "Public Policy", "type": "page"})
        internal = r1.json()
        await c.put(
            f"/api/iso-docs/pages/{internal['id']}",
            json={"content": "# Public Policy\nVisible to all.", "expected_version": 0},
        )
        await c.put(
            f"/api/iso-docs/pages/{internal['id']}/metadata",
            json={"code": "PUB01", "classification": "internal_use"},
        )

        r2 = await c.post("/api/iso-docs/nodes", json={"title": "Secret Policy", "type": "page"})
        confidential = r2.json()
        await c.put(
            f"/api/iso-docs/pages/{confidential['id']}",
            json={"content": "# Secret Policy\nRestricted.", "expected_version": 0},
        )
        await c.put(
            f"/api/iso-docs/pages/{confidential['id']}/metadata",
            json={"code": "SEC01", "classification": "confidential"},
        )

    return {"internal": internal, "confidential": confidential}


async def _client_as(token: TokenData) -> AsyncGenerator[AsyncClient, None]:
    app.dependency_overrides[get_current_user] = _override_user(token)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


class TestTreeFiltering:
    @pytest.mark.asyncio
    async def test_editor_sees_all_nodes(self, test_data: dict):
        async for c in _client_as(EDITOR_TOKEN):
            resp = await c.get("/api/iso-docs/tree")
            assert resp.status_code == 200
            ids = {n["id"] for n in resp.json()}
            assert test_data["internal"]["id"] in ids
            assert test_data["confidential"]["id"] in ids

    @pytest.mark.asyncio
    async def test_regular_user_sees_only_internal(self, test_data: dict):
        async for c in _client_as(REGULAR_TOKEN):
            resp = await c.get("/api/iso-docs/tree")
            assert resp.status_code == 200
            ids = {n["id"] for n in resp.json()}
            assert test_data["internal"]["id"] in ids
            assert test_data["confidential"]["id"] not in ids


class TestPageAccess:
    @pytest.mark.asyncio
    async def test_regular_user_can_read_internal_page(self, test_data: dict):
        async for c in _client_as(REGULAR_TOKEN):
            resp = await c.get(f"/api/iso-docs/pages/{test_data['internal']['id']}")
            assert resp.status_code == 200
            assert resp.json()["title"] == "Public Policy"

    @pytest.mark.asyncio
    async def test_regular_user_blocked_from_confidential_page(self, test_data: dict):
        async for c in _client_as(REGULAR_TOKEN):
            resp = await c.get(f"/api/iso-docs/pages/{test_data['confidential']['id']}")
            assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_editor_can_read_confidential_page(self, test_data: dict):
        async for c in _client_as(EDITOR_TOKEN):
            resp = await c.get(f"/api/iso-docs/pages/{test_data['confidential']['id']}")
            assert resp.status_code == 200
            assert resp.json()["title"] == "Secret Policy"


class TestVersionAccess:
    @pytest.mark.asyncio
    async def test_regular_user_blocked_from_confidential_versions(self, test_data: dict):
        async for c in _client_as(REGULAR_TOKEN):
            resp = await c.get(f"/api/iso-docs/pages/{test_data['confidential']['id']}/versions")
            assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_regular_user_blocked_from_confidential_version_detail(self, test_data: dict):
        async for c in _client_as(REGULAR_TOKEN):
            resp = await c.get(f"/api/iso-docs/pages/{test_data['confidential']['id']}/versions/1")
            assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_editor_can_list_confidential_versions(self, test_data: dict):
        async for c in _client_as(EDITOR_TOKEN):
            resp = await c.get(f"/api/iso-docs/pages/{test_data['confidential']['id']}/versions")
            assert resp.status_code == 200


class TestMetadataAccess:
    @pytest.mark.asyncio
    async def test_regular_user_blocked_from_confidential_metadata(self, test_data: dict):
        async for c in _client_as(REGULAR_TOKEN):
            resp = await c.get(f"/api/iso-docs/pages/{test_data['confidential']['id']}/metadata")
            assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_regular_user_can_read_internal_metadata(self, test_data: dict):
        async for c in _client_as(REGULAR_TOKEN):
            resp = await c.get(f"/api/iso-docs/pages/{test_data['internal']['id']}/metadata")
            assert resp.status_code == 200
            assert resp.json()["classification"] == "internal_use"

    @pytest.mark.asyncio
    async def test_metadata_search_excludes_confidential_for_regular_user(self, test_data: dict):
        async for c in _client_as(REGULAR_TOKEN):
            resp = await c.get("/api/iso-docs/metadata/search")
            assert resp.status_code == 200
            codes = {r["code"] for r in resp.json()}
            assert "PUB01" in codes
            assert "SEC01" not in codes

    @pytest.mark.asyncio
    async def test_metadata_search_includes_confidential_for_editor(self, test_data: dict):
        async for c in _client_as(EDITOR_TOKEN):
            resp = await c.get("/api/iso-docs/metadata/search")
            assert resp.status_code == 200
            codes = {r["code"] for r in resp.json()}
            assert "PUB01" in codes
            assert "SEC01" in codes


class TestSearchFiltering:
    @pytest.mark.asyncio
    async def test_text_search_excludes_confidential_for_regular_user(self, test_data: dict):
        async for c in _client_as(REGULAR_TOKEN):
            resp = await c.get("/api/iso-docs/pages/search?q=Policy")
            assert resp.status_code == 200
            titles = {r["title"] for r in resp.json()}
            assert "Public Policy" in titles
            assert "Secret Policy" not in titles

    @pytest.mark.asyncio
    async def test_text_search_includes_confidential_for_editor(self, test_data: dict):
        async for c in _client_as(EDITOR_TOKEN):
            resp = await c.get("/api/iso-docs/pages/search?q=Policy")
            assert resp.status_code == 200
            titles = {r["title"] for r in resp.json()}
            assert "Public Policy" in titles
            assert "Secret Policy" in titles
