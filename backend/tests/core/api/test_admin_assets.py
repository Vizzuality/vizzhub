"""Tests for admin assets API endpoints."""

from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.user import UserDB
from app.modules.iso_docs.models.node import IsoDocNodeDB
from app.modules.iso_docs.models.registry_attachment import RegistryAttachmentDB
from app.modules.iso_docs.models.registry_row import RegistryRowDB
from app.modules.iso_docs.models.registry_type import RegistryTypeDB

DEBUG_USER_ID = UUID("00000000-0000-0000-0000-000000000001")


@pytest_asyncio.fixture(autouse=True)
async def _ensure_dev_user(db_session: AsyncSession) -> None:
    from sqlalchemy import select

    result = await db_session.execute(
        select(UserDB).where(UserDB.id == DEBUG_USER_ID)
    )
    if not result.scalar_one_or_none():
        db_session.add(UserDB(id=DEBUG_USER_ID, email="dev@test.com"))
        await db_session.flush()


@pytest_asyncio.fixture
async def sample_attachment(db_session: AsyncSession) -> RegistryAttachmentDB:
    """Create a registry type, node, row, and attachment for testing."""
    rt = RegistryTypeDB(
        name="Test Type",
        slug="test-type",
        schema=[{"key": "name", "label": "Name", "type": "string", "required": True}],
    )
    db_session.add(rt)
    await db_session.flush()

    node = IsoDocNodeDB(
        title="Test Node",
        slug="test-node",
        type="registry",
        position=0,
        registry_type_id=rt.id,
    )
    db_session.add(node)
    await db_session.flush()

    row = RegistryRowDB(
        node_id=node.id,
        row_index=0,
        data={"name": "Test Row"},
    )
    db_session.add(row)
    await db_session.flush()

    attachment = RegistryAttachmentDB(
        row_id=row.id,
        node_id=node.id,
        field_key="doc",
        filename="report.pdf",
        s3_key="iso-registries/abc123-report.pdf",
        content_type="application/pdf",
        size_bytes=1024,
        uploaded_by_id=DEBUG_USER_ID,
    )
    db_session.add(attachment)
    await db_session.flush()
    return attachment


@pytest.fixture(autouse=True)
def _mock_s3_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.core.api.admin_assets.get_attachment_url",
        lambda s3_key: f"https://test-bucket/{s3_key}",
    )


@pytest.mark.asyncio
async def test_list_assets_empty(client: AsyncClient) -> None:
    resp = await client.get("/api/admin/assets")
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 0


@pytest.mark.asyncio
async def test_list_assets_with_node_title(
    client: AsyncClient, sample_attachment: RegistryAttachmentDB
) -> None:
    resp = await client.get("/api/admin/assets")
    assert resp.status_code == 200
    data = resp.json()
    assert data["total"] == 1
    item = data["items"][0]
    assert item["filename"] == "report.pdf"
    assert item["node_title"] == "Test Node"
    assert item["content_type"] == "application/pdf"
    assert item["size_bytes"] == 1024
    assert item["url"] == "https://test-bucket/iso-registries/abc123-report.pdf"


@pytest.mark.asyncio
async def test_list_assets_pagination(
    client: AsyncClient, sample_attachment: RegistryAttachmentDB
) -> None:
    resp = await client.get("/api/admin/assets", params={"page": 2, "page_size": 50})
    assert resp.status_code == 200
    data = resp.json()
    assert data["items"] == []
    assert data["total"] == 1
    assert data["page"] == 2


@pytest.mark.asyncio
async def test_list_assets_content_type_filter(
    client: AsyncClient, sample_attachment: RegistryAttachmentDB
) -> None:
    resp = await client.get("/api/admin/assets", params={"content_type": "pdf"})
    assert resp.status_code == 200
    assert resp.json()["total"] == 1

    resp = await client.get("/api/admin/assets", params={"content_type": "image"})
    assert resp.status_code == 200
    assert resp.json()["total"] == 0


@pytest.mark.asyncio
async def test_delete_asset(
    client: AsyncClient,
    sample_attachment: RegistryAttachmentDB,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "app.core.api.admin_assets.delete_attachment", lambda s3_key: None
    )

    resp = await client.delete(f"/api/admin/assets/{sample_attachment.id}")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}

    list_resp = await client.get("/api/admin/assets")
    assert list_resp.json()["total"] == 0


@pytest.mark.asyncio
async def test_delete_asset_not_found(client: AsyncClient) -> None:
    resp = await client.delete(f"/api/admin/assets/{uuid4()}")
    assert resp.status_code == 404
