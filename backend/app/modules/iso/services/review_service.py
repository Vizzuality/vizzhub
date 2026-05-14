"""Domain logic for creating access reviews from snapshots.

Shared by the manual capture API endpoint and the monthly cron job so both
paths produce identical AccessReview rows (diff vs the previous snapshot of
the same provider, plus one AccessReviewAction per change).
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.iso.models.access_review import AccessReviewDB
from app.modules.iso.models.access_snapshot import AccessSnapshotDB
from app.modules.iso.schemas import ReviewStatus
from app.modules.iso.services.diff_engine import (
    build_diff_summary,
    compute_diff,
    create_review_actions,
)

DEFAULT_REVIEW_SCOPE = "All users and groups"


def _diff_context(snapshot: AccessSnapshotDB) -> str:
    """Return the provider-specific identifier used by the diff engine."""
    metadata = snapshot.source_metadata or {}
    if snapshot.provider == "github":
        return metadata.get("org", "")
    if snapshot.provider == "jira":
        return metadata.get("site_url", "")
    return metadata.get("domain", "")


async def create_review_for_snapshot(
    db: AsyncSession,
    snapshot: AccessSnapshotDB,
    reviewer_id: UUID | None = None,
) -> AccessReviewDB:
    """Create a DRAFT AccessReview for the given snapshot.

    Finds the most recent prior snapshot of the same provider, computes the
    diff, persists the review and one action per change. The caller is
    responsible for committing the transaction.
    """
    previous_result = await db.execute(
        select(AccessSnapshotDB)
        .where(AccessSnapshotDB.provider == snapshot.provider)
        .where(AccessSnapshotDB.id != snapshot.id)
        .where(AccessSnapshotDB.captured_at < snapshot.captured_at)
        .order_by(AccessSnapshotDB.captured_at.desc())
        .limit(1)
    )
    previous = previous_result.scalar_one_or_none()

    review = AccessReviewDB(
        snapshot_id=snapshot.id,
        previous_snapshot_id=previous.id if previous else None,
        reviewer_id=reviewer_id,
        status=ReviewStatus.DRAFT,
        scope=DEFAULT_REVIEW_SCOPE,
    )
    db.add(review)
    await db.flush()

    if previous:
        changes = compute_diff(
            snapshot.data, previous.data, _diff_context(snapshot), snapshot.provider
        )
        review.diff_summary = build_diff_summary(changes)
        await create_review_actions(db, review.id, changes)
        await db.flush()

    return review
