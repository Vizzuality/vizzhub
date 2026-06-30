"""Service tests for merge_clients (core)."""

import pytest
from sqlalchemy import select

from app.core.models.client import ClientDB
from app.core.models.project import ProjectDB
from app.core.services.client_service import merge_clients


@pytest.mark.asyncio
async def test_merge_reassigns_projects_and_deactivates_source(db_session):
    target = ClientDB(name="Canonical", slug="canonical")
    source = ClientDB(name="Variant", slug="variant")
    db_session.add_all([target, source])
    await db_session.flush()
    db_session.add(ProjectDB(name="P1", client_id=source.id))
    await db_session.flush()

    moved = await merge_clients(db_session, target_id=target.id, source_ids=[source.id])
    await db_session.flush()

    assert moved == 1
    refreshed_source = await db_session.get(ClientDB, source.id)
    assert refreshed_source.is_active is False
    project = (
        await db_session.execute(select(ProjectDB).where(ProjectDB.client_id == target.id))
    ).scalar_one()
    assert project.client_id == target.id


@pytest.mark.asyncio
async def test_merge_rejects_target_in_sources(db_session):
    c = ClientDB(name="X", slug="x")
    db_session.add(c)
    await db_session.flush()
    with pytest.raises(ValueError):
        await merge_clients(db_session, target_id=c.id, source_ids=[c.id])


@pytest.mark.asyncio
async def test_merge_rejects_empty_source_ids(db_session):
    c = ClientDB(name="Target", slug="target-only")
    db_session.add(c)
    await db_session.flush()
    with pytest.raises(ValueError, match="source_ids must not be empty"):
        await merge_clients(db_session, target_id=c.id, source_ids=[])


@pytest.mark.asyncio
async def test_merge_rejects_nonexistent_ids(db_session):
    from uuid import uuid4

    c = ClientDB(name="Real", slug="real")
    db_session.add(c)
    await db_session.flush()
    with pytest.raises(ValueError, match="do not exist"):
        await merge_clients(db_session, target_id=c.id, source_ids=[uuid4()])
