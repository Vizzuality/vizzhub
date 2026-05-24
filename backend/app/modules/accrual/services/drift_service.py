"""Drift finding service: list, summarise, resolve, reopen."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

import structlog
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.project import ProjectDB
from app.modules.accrual.models.accrual_drift_finding import AccrualDriftFindingDB

logger = structlog.get_logger()


class DriftFindingError(Exception):
    """Base exception for drift-service domain errors."""


class DriftFindingNotFound(DriftFindingError):
    """Finding ID not present."""


async def list_findings(
    db: AsyncSession,
    *,
    kinds: list[str] | None = None,
    resolved: bool | None = None,
    project_id: UUID | None = None,
    excel_code: str | None = None,
    limit: int = 200,
    offset: int = 0,
) -> tuple[list[tuple[AccrualDriftFindingDB, ProjectDB | None]], int]:
    """Return ``(rows, total)`` matching the filters.

    Each ``row`` is the finding + the project (joined; may be None for
    ``missing_tracker`` findings).
    """
    filters = []
    if kinds:
        filters.append(AccrualDriftFindingDB.kind.in_(kinds))
    if resolved is True:
        filters.append(AccrualDriftFindingDB.resolved_at.is_not(None))
    elif resolved is False:
        filters.append(AccrualDriftFindingDB.resolved_at.is_(None))
    if project_id is not None:
        filters.append(AccrualDriftFindingDB.project_id == project_id)
    if excel_code:
        filters.append(AccrualDriftFindingDB.excel_code == excel_code)

    stmt = (
        select(AccrualDriftFindingDB, ProjectDB)
        .outerjoin(ProjectDB, ProjectDB.id == AccrualDriftFindingDB.project_id)
        .where(*filters)
    )
    count_stmt = select(func.count()).select_from(AccrualDriftFindingDB).where(*filters)

    # Unresolved first, then grouped by project name so multiple findings
    # affecting the same tracker project appear consecutive (extensions,
    # multi-Excel → 1 tracker, several divergence kinds for the same project).
    # Within a project group, most-recent detection first.
    stmt = (
        stmt.order_by(
            case((AccrualDriftFindingDB.resolved_at.is_(None), 0), else_=1),
            ProjectDB.name.asc().nullslast(),
            AccrualDriftFindingDB.detected_at.desc(),
        )
        .limit(limit)
        .offset(offset)
    )

    rows = list((await db.execute(stmt)).all())
    total = (await db.execute(count_stmt)).scalar_one()
    return [(r[0], r[1]) for r in rows], total


async def summary(db: AsyncSession) -> dict:
    """Return ``{ by_kind: {kind: {open, resolved}}, total_open, total_resolved }``."""
    stmt = select(
        AccrualDriftFindingDB.kind,
        AccrualDriftFindingDB.resolved_at.is_(None).label("is_open"),
        func.count().label("count"),
    ).group_by(AccrualDriftFindingDB.kind, AccrualDriftFindingDB.resolved_at.is_(None))
    rows = (await db.execute(stmt)).all()

    by_kind: dict[str, dict[str, int]] = {}
    total_open = 0
    total_resolved = 0
    for kind, is_open, count in rows:
        bucket = by_kind.setdefault(kind, {"open": 0, "resolved": 0})
        if is_open:
            bucket["open"] += count
            total_open += count
        else:
            bucket["resolved"] += count
            total_resolved += count
    return {
        "by_kind": by_kind,
        "total_open": total_open,
        "total_resolved": total_resolved,
    }


async def get_finding(db: AsyncSession, finding_id: UUID) -> AccrualDriftFindingDB:
    finding = (
        await db.execute(
            select(AccrualDriftFindingDB).where(AccrualDriftFindingDB.id == finding_id)
        )
    ).scalar_one_or_none()
    if finding is None:
        raise DriftFindingNotFound(f"Drift finding {finding_id} not found")
    return finding


async def resolve(
    db: AsyncSession,
    *,
    finding_id: UUID,
    resolution: str,
    resolved_by: UUID | None,
) -> AccrualDriftFindingDB:
    """Mark a finding as resolved with a free-text note.

    Idempotent: re-resolving an already-resolved finding overwrites the
    resolution text and timestamp.
    """
    finding = await get_finding(db, finding_id)
    finding.resolution = resolution
    finding.resolved_at = datetime.now(UTC)
    finding.resolved_by = resolved_by
    await db.flush()
    logger.info(
        "accrual_drift_resolved",
        finding_id=str(finding_id),
        kind=finding.kind,
        project_id=str(finding.project_id) if finding.project_id else None,
        excel_code=finding.excel_code,
        resolved_by=str(resolved_by) if resolved_by else None,
    )
    return finding


async def reopen(db: AsyncSession, *, finding_id: UUID) -> AccrualDriftFindingDB:
    """Clear the resolution on a finding so it shows as open again."""
    finding = await get_finding(db, finding_id)
    finding.resolution = None
    finding.resolved_at = None
    finding.resolved_by = None
    await db.flush()
    logger.info(
        "accrual_drift_reopened",
        finding_id=str(finding_id),
        kind=finding.kind,
    )
    return finding
