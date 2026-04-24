"""RSVP service: set, remove, query per-user RSVPs on events."""

from typing import Literal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.models.user import UserDB
from app.core.sql_helpers import user_display_name_expr
from app.modules.events.models.event_rsvp import EventRsvpDB


RsvpStatusValue = Literal["going", "maybe", "not_going"]


async def set_rsvp(
    db: AsyncSession,
    event_id: UUID,
    user_id: UUID,
    status: RsvpStatusValue,
) -> EventRsvpDB:
    stmt = (
        pg_insert(EventRsvpDB)
        .values(event_id=event_id, user_id=user_id, status=status)
        .on_conflict_do_update(
            index_elements=["event_id", "user_id"],
            set_={"status": status},
        )
        .returning(EventRsvpDB)
    )
    result = await db.execute(stmt)
    await db.flush()
    return result.scalar_one()


async def remove_rsvp(db: AsyncSession, event_id: UUID, user_id: UUID) -> bool:
    existing = (
        await db.execute(
            select(EventRsvpDB).where(
                EventRsvpDB.event_id == event_id,
                EventRsvpDB.user_id == user_id,
            )
        )
    ).scalar_one_or_none()
    if existing is None:
        return False
    await db.delete(existing)
    await db.flush()
    return True


async def get_rsvps_for_event(
    db: AsyncSession, event_id: UUID
) -> dict[str, list[dict]]:
    user_alias = aliased(UserDB)
    stmt = (
        select(
            EventRsvpDB.status,
            user_alias.id,
            user_alias.first_name,
            user_alias.last_name,
            user_alias.email,
        )
        .join(user_alias, user_alias.id == EventRsvpDB.user_id)
        .where(EventRsvpDB.event_id == event_id)
        .order_by(user_display_name_expr(user_alias))
    )
    out: dict[str, list[dict]] = {"going": [], "maybe": [], "not_going": []}
    for status, uid, first, last, email in (await db.execute(stmt)).all():
        out[status].append(
            {"id": uid, "first_name": first, "last_name": last, "email": email}
        )
    return out
