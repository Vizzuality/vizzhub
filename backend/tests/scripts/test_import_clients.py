"""Tests for the idempotent client importer."""

import pytest
from sqlalchemy import func, select

from app.core.models.client import ClientDB
from app.scripts.import_clients import import_clients


@pytest.mark.asyncio
async def test_colliding_slugs_kept_separate(db_session):
    entries = [
        {"name": "Acme, Inc.", "code": None, "primary_contact": None},
        {"name": "Acme Inc", "code": None, "primary_contact": None},
    ]
    stats = await import_clients(db_session, entries)
    assert stats["created"] == 2
    slugs = (
        (await db_session.execute(select(ClientDB.slug).order_by(ClientDB.slug))).scalars().all()
    )
    assert slugs == ["acme-inc", "acme-inc-2"]


@pytest.mark.asyncio
async def test_duplicate_code_cleared_on_later_row(db_session):
    entries = [
        {"name": "First Co", "code": "DUP", "primary_contact": None},
        {"name": "Second Co", "code": "DUP", "primary_contact": None},
    ]
    stats = await import_clients(db_session, entries)
    assert stats["codes_cleared"] == 1
    first = (
        await db_session.execute(select(ClientDB).where(ClientDB.slug == "first-co"))
    ).scalar_one()
    second = (
        await db_session.execute(select(ClientDB).where(ClientDB.slug == "second-co"))
    ).scalar_one()
    assert first.code == "DUP"
    assert second.code is None


@pytest.mark.asyncio
async def test_import_is_idempotent(db_session):
    entries = [
        {"name": "Stable Org", "code": "S1", "primary_contact": "Jane"},
        {"name": "Stable Org", "code": "S1", "primary_contact": "Jane"},
    ]
    await import_clients(db_session, entries)
    second = await import_clients(db_session, entries)
    # Re-running creates nothing new; the same rows are matched and updated.
    assert second["created"] == 0
    total = (await db_session.execute(select(func.count()).select_from(ClientDB))).scalar_one()
    assert total == 2
    # The row that kept the code still keeps it after re-run (self is excluded).
    kept = (
        await db_session.execute(select(ClientDB).where(ClientDB.slug == "stable-org"))
    ).scalar_one()
    assert kept.code == "S1"
