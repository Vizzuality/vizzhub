"""Client merge logic (core)."""

from uuid import UUID

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.client import ClientDB
from app.core.models.project import ProjectDB

logger = structlog.get_logger()


async def merge_clients(db: AsyncSession, *, target_id: UUID, source_ids: list[UUID]) -> int:
    """Reassign all projects from source clients to target, then deactivate sources.

    Returns the number of projects reassigned.
    Raises ValueError if target is among sources, source_ids is empty, or any id missing.
    """
    if not source_ids:
        raise ValueError("source_ids must not be empty")
    if target_id in source_ids:
        raise ValueError("target_id cannot be among source_ids")

    ids = [target_id, *source_ids]
    found = (await db.execute(select(ClientDB.id).where(ClientDB.id.in_(ids)))).scalars().all()
    if set(found) != set(ids):
        raise ValueError("one or more client ids do not exist")

    result = await db.execute(
        update(ProjectDB).where(ProjectDB.client_id.in_(source_ids)).values(client_id=target_id)
    )
    moved = result.rowcount or 0
    await db.execute(update(ClientDB).where(ClientDB.id.in_(source_ids)).values(is_active=False))
    await _inherit_copper_link(db, target_id=target_id, source_ids=source_ids)
    logger.info(
        "clients_merged",
        target_id=str(target_id),
        source_ids=[str(s) for s in source_ids],
        moved_projects=moved,
    )
    return moved


async def _inherit_copper_link(
    db: AsyncSession, *, target_id: UUID, source_ids: list[UUID]
) -> None:
    """Give an unlinked target the Copper company of the first linked source.

    The link moves rather than copies: a Copper company maps to one client.
    """
    target = await db.get(ClientDB, target_id)
    if target is None or target.copper_company_id is not None:
        return
    source = (
        await db.execute(
            select(ClientDB)
            .where(ClientDB.id.in_(source_ids), ClientDB.copper_company_id.is_not(None))
            .order_by(ClientDB.name)
            .limit(1)
        )
    ).scalar_one_or_none()
    if source is None:
        return
    copper_company_id = source.copper_company_id
    source.copper_company_id = None
    await db.flush()
    target.copper_company_id = copper_company_id
    logger.info(
        "client_copper_link_moved",
        target_id=str(target_id),
        source_id=str(source.id),
        copper_company_id=copper_company_id,
    )
