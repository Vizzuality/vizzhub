"""Tests for drive_lookup computed column enrichment."""

import pytest
import pytest_asyncio
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.iso_docs.models.drive_mapping import IsoDocDriveMappingDB
from app.modules.iso_docs.models.node import IsoDocNodeDB
from app.modules.iso_docs.services.registry_service import (
    build_drive_url,
    extract_drive_lookup_columns,
    extract_slug_from_link,
)

DRIVE_LOOKUP_SCHEMA = [
    {"key": "document", "label": "Document", "type": "string", "required": True},
    {"key": "link", "label": "Link", "type": "url", "required": False},
    {
        "key": "drive_link",
        "label": "Google Drive",
        "type": "computed",
        "formula": {"operation": "drive_lookup", "fields": ["link"]},
    },
]


# -----------------------------------------------------------------------
# Unit tests — pure helpers
# -----------------------------------------------------------------------


def test_extract_drive_lookup_columns_found():
    cols = extract_drive_lookup_columns(DRIVE_LOOKUP_SCHEMA)
    assert cols == [("drive_link", "link")]


def test_extract_drive_lookup_columns_empty_for_regular_computed():
    schema = [
        {"key": "total", "type": "computed", "label": "T",
         "formula": {"operation": "sum", "fields": ["a", "b"]}},
    ]
    assert extract_drive_lookup_columns(schema) == []


def test_extract_slug_from_link_full_url():
    assert extract_slug_from_link("/iso/docs?page=my-policy") == "my-policy"


def test_extract_slug_from_link_hub_url():
    assert extract_slug_from_link(
        "https://hub.vizzuality.com/iso/docs?page=access-control-policy"
    ) == "access-control-policy"


def test_extract_slug_from_link_none():
    assert extract_slug_from_link(None) is None
    assert extract_slug_from_link("") is None
    assert extract_slug_from_link("not-a-link") is None


def test_build_drive_url_document():
    assert build_drive_url("abc", "document") == "https://docs.google.com/document/d/abc/edit"


def test_build_drive_url_spreadsheet():
    assert build_drive_url("xyz", "spreadsheet") == "https://docs.google.com/spreadsheets/d/xyz/edit"


def test_build_drive_url_folder():
    assert build_drive_url("f1", "folder") == "https://drive.google.com/drive/folders/f1"


def test_build_drive_url_unknown_type():
    url = build_drive_url("u1", "presentation")
    assert url == "https://drive.google.com/file/d/u1/view"


# -----------------------------------------------------------------------
# Integration test — API resolves drive_lookup on list_rows
# -----------------------------------------------------------------------


@pytest_asyncio.fixture
async def drive_lookup_setup(
    client: AsyncClient, db_session: AsyncSession,
) -> dict:
    """Create registry with drive_lookup schema + a target page with Drive mapping."""
    rt_resp = await client.post(
        "/api/iso-docs/registry-types",
        json={"name": "Doc Control Test", "schema": DRIVE_LOOKUP_SCHEMA},
    )
    rt = rt_resp.json()

    node_resp = await client.post(
        "/api/iso-docs/nodes",
        json={
            "title": "Doc Control Registry",
            "type": "registry",
            "registry_type_id": rt["id"],
        },
    )
    node = node_resp.json()

    target_page = IsoDocNodeDB(
        title="My Policy",
        slug="my-policy",
        type="page",
        position=0,
    )
    db_session.add(target_page)
    await db_session.flush()
    await db_session.refresh(target_page)

    mapping = IsoDocDriveMappingDB(
        node_id=target_page.id,
        drive_file_id="1AbcDef_DriveId",
        drive_file_type="document",
    )
    db_session.add(mapping)
    await db_session.flush()

    return {"node": node, "target_slug": target_page.slug}


@pytest.mark.asyncio
async def test_list_rows_resolves_drive_lookup(
    client: AsyncClient, drive_lookup_setup: dict,
):
    node_id = drive_lookup_setup["node"]["id"]

    await client.post(
        f"/api/iso-docs/registries/{node_id}/rows",
        json={
            "data": {
                "document": "My Policy",
                "link": "/iso/docs?page=my-policy",
            },
        },
    )

    resp = await client.get(f"/api/iso-docs/registries/{node_id}/rows")
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["data"]["drive_link"] == (
        "https://docs.google.com/document/d/1AbcDef_DriveId/edit"
    )


@pytest.mark.asyncio
async def test_list_rows_drive_lookup_no_mapping(
    client: AsyncClient, drive_lookup_setup: dict,
):
    """Row with a slug that has no Drive mapping gets None."""
    node_id = drive_lookup_setup["node"]["id"]

    await client.post(
        f"/api/iso-docs/registries/{node_id}/rows",
        json={
            "data": {
                "document": "Unknown Doc",
                "link": "/iso/docs?page=nonexistent-doc",
            },
        },
    )

    resp = await client.get(f"/api/iso-docs/registries/{node_id}/rows")
    rows = resp.json()
    unmapped = [r for r in rows if r["data"]["document"] == "Unknown Doc"]
    assert len(unmapped) == 1
    assert unmapped[0]["data"]["drive_link"] is None
