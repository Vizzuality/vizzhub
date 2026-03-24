"""Tests for generic content version service."""

import pytest
from uuid import uuid4

from app.core.services.content_version_service import ContentVersionService
from app.modules.playbook.models.node import PlaybookNodeDB  # registers playbook_nodes in Base.metadata
from app.modules.playbook.models.page_version import PlaybookPageVersionDB


@pytest.fixture
def version_service():
    return ContentVersionService(
        model_class=PlaybookPageVersionDB,
        entity_fk_field="node_id",
    )


async def _create_node(db_session, node_id=None):
    """Insert a minimal PlaybookNodeDB row to satisfy the FK constraint."""
    nid = node_id or uuid4()
    node = PlaybookNodeDB(
        id=nid,
        title="Test Node",
        slug=str(nid),
        type="page",
    )
    db_session.add(node)
    await db_session.flush()
    return nid


@pytest.mark.asyncio
async def test_save_first_version(db_session, version_service):
    node_id = await _create_node(db_session)
    version_num, conflict = await version_service.save_version(
        db_session, entity_id=node_id, content="# Hello", user_id=None
    )
    assert version_num == 1
    assert conflict is False


@pytest.mark.asyncio
async def test_save_increments_version(db_session, version_service):
    node_id = await _create_node(db_session)
    v1, _ = await version_service.save_version(
        db_session, entity_id=node_id, content="v1", user_id=None
    )
    v2, _ = await version_service.save_version(
        db_session, entity_id=node_id, content="v2", user_id=None
    )
    assert v1 == 1
    assert v2 == 2


@pytest.mark.asyncio
async def test_get_latest(db_session, version_service):
    node_id = await _create_node(db_session)
    await version_service.save_version(
        db_session, entity_id=node_id, content="old", user_id=None
    )
    await version_service.save_version(
        db_session, entity_id=node_id, content="new", user_id=None
    )
    latest = await version_service.get_latest(db_session, entity_id=node_id)
    assert latest is not None
    assert latest.content == "new"
    assert latest.version == 2


@pytest.mark.asyncio
async def test_get_latest_returns_none_for_missing(db_session, version_service):
    result = await version_service.get_latest(db_session, entity_id=uuid4())
    assert result is None


@pytest.mark.asyncio
async def test_get_specific_version(db_session, version_service):
    node_id = await _create_node(db_session)
    await version_service.save_version(
        db_session, entity_id=node_id, content="v1", user_id=None
    )
    await version_service.save_version(
        db_session, entity_id=node_id, content="v2", user_id=None
    )
    result = await version_service.get_version(db_session, entity_id=node_id, version=1)
    assert result is not None
    assert result.content == "v1"


@pytest.mark.asyncio
async def test_get_version_returns_none_for_missing(db_session, version_service):
    result = await version_service.get_version(
        db_session, entity_id=uuid4(), version=99
    )
    assert result is None


@pytest.mark.asyncio
async def test_list_versions(db_session, version_service):
    node_id = await _create_node(db_session)
    await version_service.save_version(
        db_session, entity_id=node_id, content="v1", user_id=None
    )
    await version_service.save_version(
        db_session, entity_id=node_id, content="v2", user_id=None
    )
    versions = await version_service.list_versions(db_session, entity_id=node_id)
    assert len(versions) == 2
    assert versions[0].version == 2
    assert versions[1].version == 1
