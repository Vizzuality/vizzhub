"""Shared test fixtures for the ISO module."""

from datetime import datetime, timezone
from uuid import UUID

from app.core.models.user import UserDB
from app.modules.iso.models.access_review import AccessReviewDB
from app.modules.iso.models.access_review_action import AccessReviewActionDB
from app.modules.iso.models.access_snapshot import AccessSnapshotDB

DEV_USER_ID = UUID("00000000-0000-0000-0000-000000000001")


async def ensure_dev_user(db_session) -> None:
    """Create the dev user in the DB so FK constraints pass."""
    from sqlalchemy import select

    result = await db_session.execute(
        select(UserDB).where(UserDB.id == DEV_USER_ID)
    )
    if not result.scalar_one_or_none():
        db_session.add(UserDB(id=DEV_USER_ID, email="dev@test.com"))
        await db_session.flush()


async def make_snapshot(
    db_session, captured_at=None, **kwargs
) -> AccessSnapshotDB:
    defaults = {
        "provider": "google_workspace",
        "captured_at": captured_at or datetime(2026, 2, 1, tzinfo=timezone.utc),
        "data_version": "1",
        "source_metadata": {"domain": "test.com"},
        "data": {"users": []},
        "summary": {"total_users": 0},
    }
    defaults.update(kwargs)
    snapshot = AccessSnapshotDB(**defaults)
    db_session.add(snapshot)
    await db_session.flush()
    return snapshot


async def make_review(
    db_session, snapshot_id, status: str = "draft", **kwargs
) -> AccessReviewDB:
    defaults = {
        "snapshot_id": snapshot_id,
        "status": status,
        "scope": "All users and groups",
    }
    defaults.update(kwargs)
    review = AccessReviewDB(**defaults)
    db_session.add(review)
    await db_session.flush()
    return review


async def make_action(
    db_session, review_id, **kwargs
) -> AccessReviewActionDB:
    defaults = {
        "review_id": review_id,
        "subject_type": "user",
        "subject_id": "u1",
        "subject_label": "User One",
        "change_type": "new_user",
    }
    defaults.update(kwargs)
    action = AccessReviewActionDB(**defaults)
    db_session.add(action)
    await db_session.flush()
    return action
