"""Planner write operations shared by the REST API and the MCP command handler."""

from datetime import date
from uuid import UUID

from sqlalchemy import delete, func, tuple_
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.capacity.models.capacity_plan import CapacityPlanDB, CellUpdate


async def _upsert_batch(
    db: AsyncSession,
    batch: list,
    user_id: UUID,
    include_comment: bool,
) -> None:
    """Upsert a batch of cells. When include_comment is False the existing
    DB comment is preserved (percentage-only update)."""
    values = [
        {
            "project_id": cell.project_id,
            "user_id": cell.user_id,
            "week_start": cell.week_start,
            "percentage": cell.percentage,
            "comment": cell.comment,
            "created_by": user_id,
            "updated_by": user_id,
        }
        for cell in batch
    ]
    stmt = pg_insert(CapacityPlanDB).values(values)
    update_set: dict = {
        "percentage": stmt.excluded.percentage,
        "updated_by": stmt.excluded.updated_by,
        "updated_at": func.now(),
    }
    if include_comment:
        update_set["comment"] = stmt.excluded.comment
    stmt = stmt.on_conflict_do_update(
        constraint="uq_capacity_plan_cell",
        set_=update_set,
    )
    await db.execute(stmt)


async def apply_cell_updates(
    db: AsyncSession,
    updates: list[CellUpdate],
    actor_id: UUID | str,
) -> dict[str, int]:
    """Upsert or delete planner cells. A percentage of None or 0 deletes the cell.

    A cell whose ``comment`` was not explicitly set keeps its stored comment.
    """
    deletes = [c for c in updates if not c.percentage]
    upserts = [c for c in updates if c.percentage]

    deleted = 0
    if deletes:
        result = await db.execute(
            delete(CapacityPlanDB).where(
                tuple_(
                    CapacityPlanDB.project_id,
                    CapacityPlanDB.user_id,
                    CapacityPlanDB.week_start,
                ).in_([(c.project_id, c.user_id, c.week_start) for c in deletes])
            )
        )
        deleted = result.rowcount

    if upserts:
        with_comment = [c for c in upserts if "comment" in c.model_fields_set]
        without_comment = [c for c in upserts if "comment" not in c.model_fields_set]
        if with_comment:
            await _upsert_batch(db, with_comment, actor_id, include_comment=True)
        if without_comment:
            await _upsert_batch(db, without_comment, actor_id, include_comment=False)

    await db.flush()
    return {"upserted": len(upserts), "deleted": deleted}


async def clear_assignment_from(
    db: AsyncSession,
    *,
    project_id: UUID,
    user_id: UUID,
    from_week: date,
) -> int:
    """Delete a person's planned weeks on a project from ``from_week`` onward."""
    result = await db.execute(
        delete(CapacityPlanDB).where(
            CapacityPlanDB.project_id == project_id,
            CapacityPlanDB.user_id == user_id,
            CapacityPlanDB.week_start >= from_week,
        )
    )
    await db.flush()
    return result.rowcount
