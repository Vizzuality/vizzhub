"""Tests for the collect_iso_snapshot cron job recovery + review-creation paths."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.iso.models.access_review import AccessReviewDB
from app.modules.iso.models.access_review_action import AccessReviewActionDB
from app.modules.iso.models.access_snapshot import AccessSnapshotDB
from app.worker.collect_iso_snapshot import collect_iso_snapshot


def _fake_snapshot(provider: str, captured_at: datetime, data: dict) -> AccessSnapshotDB:
    return AccessSnapshotDB(
        provider=provider,
        captured_at=captured_at,
        data_version="1",
        source_metadata={"domain": "test.com"},
        data=data,
        summary={},
    )


@pytest.mark.asyncio
async def test_cron_creates_draft_review_for_each_connected_provider(
    db_session: AsyncSession,
) -> None:
    """Regression: the cron job used to capture snapshots without creating reviews."""

    async def fake_gw_capture(self, run_mode: str = "cron", **_):
        snap = _fake_snapshot(
            "google_workspace",
            datetime(2026, 5, 1, 6, tzinfo=timezone.utc),
            {"users": [], "groups": [], "group_members": {}, "role_assignments": []},
        )
        db_session.add(snap)
        await db_session.flush()
        return snap

    ctx = {"db": db_session}

    with (
        patch(
            "app.worker.collect_iso_snapshot._is_gw_connected",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "app.worker.collect_iso_snapshot._is_github_connected",
            new=AsyncMock(return_value=False),
        ),
        patch(
            "app.worker.collect_iso_snapshot._is_jira_connected",
            new=AsyncMock(return_value=False),
        ),
        patch(
            "app.modules.iso.services.collectors.google_workspace.GoogleWorkspaceCollector.capture",
            new=fake_gw_capture,
        ),
    ):
        result = await collect_iso_snapshot(ctx)

    assert result["status"] == "completed"
    assert "google_workspace" in result["providers"]
    assert "review_id" in result["providers"]["google_workspace"]

    rows = (await db_session.execute(select(AccessReviewDB))).scalars().all()
    assert len(rows) == 1
    review = rows[0]
    assert review.status == "draft"
    assert review.scope == "All users and groups"
    assert review.previous_snapshot_id is None  # first snapshot, no prior


@pytest.mark.asyncio
async def test_cron_review_links_previous_snapshot_and_computes_diff(
    db_session: AsyncSession,
) -> None:
    """When a previous snapshot exists, the cron review must link it and persist actions."""
    previous = _fake_snapshot(
        "google_workspace",
        datetime(2026, 4, 1, 6, tzinfo=timezone.utc),
        {
            "users": [{"email": "a@test.com", "name": "A", "is_admin": False}],
            "groups": [],
            "group_members": {},
            "role_assignments": [],
        },
    )
    db_session.add(previous)
    await db_session.flush()
    previous_id = previous.id

    async def fake_gw_capture(self, run_mode: str = "cron", **_):
        snap = _fake_snapshot(
            "google_workspace",
            datetime(2026, 5, 1, 6, tzinfo=timezone.utc),
            {
                "users": [
                    {"email": "a@test.com", "name": "A", "is_admin": False},
                    {"email": "b@test.com", "name": "B", "is_admin": False},
                ],
                "groups": [],
                "group_members": {},
                "role_assignments": [],
            },
        )
        db_session.add(snap)
        await db_session.flush()
        return snap

    ctx = {"db": db_session}

    with (
        patch(
            "app.worker.collect_iso_snapshot._is_gw_connected",
            new=AsyncMock(return_value=True),
        ),
        patch(
            "app.worker.collect_iso_snapshot._is_github_connected",
            new=AsyncMock(return_value=False),
        ),
        patch(
            "app.worker.collect_iso_snapshot._is_jira_connected",
            new=AsyncMock(return_value=False),
        ),
        patch(
            "app.modules.iso.services.collectors.google_workspace.GoogleWorkspaceCollector.capture",
            new=fake_gw_capture,
        ),
    ):
        await collect_iso_snapshot(ctx)

    review = (await db_session.execute(select(AccessReviewDB))).scalar_one()
    assert review.previous_snapshot_id == previous_id

    actions = (
        (await db_session.execute(
            select(AccessReviewActionDB).where(AccessReviewActionDB.review_id == review.id)
        )).scalars().all()
    )
    assert len(actions) >= 1, "expected at least one diff action for the new user b@test.com"
