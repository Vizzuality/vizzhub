"""Line-level CRUD + project links for the accrual module.

A line is the revenue-recognition unit; this service owns its lifecycle
(create/update/delete) and its 0..N links to projects. Cell values live in
``cell_service`` (keyed by ``line_id``). Callers own the transaction.
"""

from datetime import date
from decimal import Decimal
from uuid import UUID

import structlog
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.accrual.models.accrual_line import AccrualLineDB, LineSource
from app.modules.accrual.models.accrual_line_project import AccrualLineProjectDB

logger = structlog.get_logger()

_UPDATABLE_FIELDS = frozenset(
    {"name", "value_eur", "value_orig", "currency", "window_start", "window_end"}
)


async def create_line(
    db: AsyncSession,
    *,
    name: str | None,
    value_eur: Decimal,
    value_orig: Decimal | None,
    currency: str | None,
    window_start: date | None,
    window_end: date | None,
    project_ids: list[UUID],
    created_by: UUID | None,
) -> AccrualLineDB:
    """Create a ``manual`` line and link it to the given projects."""
    line = AccrualLineDB(
        name=name,
        source=LineSource.MANUAL.value,
        value_eur=value_eur,
        value_orig=value_orig,
        currency=currency,
        window_start=window_start,
        window_end=window_end,
        created_by=created_by,
    )
    db.add(line)
    await db.flush()
    for project_id in dict.fromkeys(project_ids):
        db.add(AccrualLineProjectDB(line_id=line.id, project_id=project_id))
    await db.flush()
    logger.info(
        "accrual_line_created",
        line_id=str(line.id),
        project_count=len(set(project_ids)),
        user_id=str(created_by) if created_by else None,
    )
    return line


async def update_line(db: AsyncSession, *, line_id: UUID, fields: dict) -> AccrualLineDB | None:
    """Apply only the supplied (``model_fields_set``) fields to a line."""
    line = await db.get(AccrualLineDB, line_id)
    if line is None:
        return None
    for key, value in fields.items():
        if key in _UPDATABLE_FIELDS:
            setattr(line, key, value)
    await db.flush()
    logger.info("accrual_line_updated", line_id=str(line_id), fields=sorted(fields))
    return line


async def delete_line(db: AsyncSession, *, line_id: UUID) -> bool:
    """Delete a line (cells + links cascade in the DB). Returns False if absent."""
    line = await db.get(AccrualLineDB, line_id)
    if line is None:
        return False
    await db.delete(line)
    await db.flush()
    logger.info("accrual_line_deleted", line_id=str(line_id))
    return True


async def link_project(db: AsyncSession, *, line_id: UUID, project_id: UUID) -> bool:
    """Link a project to a line. Idempotent — returns False if already linked."""
    existing = await db.execute(
        select(AccrualLineProjectDB).where(
            AccrualLineProjectDB.line_id == line_id,
            AccrualLineProjectDB.project_id == project_id,
        )
    )
    if existing.scalar_one_or_none() is not None:
        return False
    db.add(AccrualLineProjectDB(line_id=line_id, project_id=project_id))
    await db.flush()
    logger.info("accrual_line_project_linked", line_id=str(line_id), project_id=str(project_id))
    return True


async def unlink_project(db: AsyncSession, *, line_id: UUID, project_id: UUID) -> bool:
    """Remove a line↔project link. Returns False if it was not linked."""
    result = await db.execute(
        delete(AccrualLineProjectDB).where(
            AccrualLineProjectDB.line_id == line_id,
            AccrualLineProjectDB.project_id == project_id,
        )
    )
    await db.flush()
    if result.rowcount:
        logger.info(
            "accrual_line_project_unlinked", line_id=str(line_id), project_id=str(project_id)
        )
    return bool(result.rowcount)
