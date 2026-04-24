"""RSVP service: set, remove, query per-user RSVPs on events."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.models.user import UserDB
from app.core.sql_helpers import user_display_name_expr
from app.modules.events.models.event_rsvp import EventRsvpDB


async def set_rsvp(
    db: AsyncSession, event_id: UUID, user_id: UUID, status: str
) -> EventRsvpDB:
    existing = (
        await db.execute(
            select(EventRsvpDB).where(
                EventRsvpDB.event_id == event_id,
                EventRsvpDB.user_id == user_id,
            )
        )
    ).scalar_one_or_none()

    if existing is None:
        rsvp = EventRsvpDB(event_id=event_id, user_id=user_id, status=status)
        db.add(rsvp)
        await db.flush()
        return rsvp

    existing.status = status
    await db.flush()
    return existing


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
            user_alias.id, user_alias.first_name, user_alias.last_name,
            user_alias.email,
        )
        .join(user_alias, user_alias.id == EventRsvpDB.user_id)
        .where(EventRsvpDB.event_id == event_id)
        .order_by(user_display_name_expr(user_alias))
    )
    out: dict[str, list[dict]] = {"going": [], "maybe": [], "not_going": []}
    for status, uid, first, last, email in (await db.execute(stmt)).all():
        out[status].append({
            "id": uid, "first_name": first, "last_name": last, "email": email,
        })
    return out
