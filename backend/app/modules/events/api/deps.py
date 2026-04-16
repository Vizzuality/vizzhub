"""Events API dependencies."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TokenData
from app.core.permissions import Action, require_permission
from app.modules.events.models.event import EventDB

EventsViewer = Annotated[TokenData, Depends(require_permission(Action.EVENTS_VIEW))]
EventsManager = Annotated[TokenData, Depends(require_permission(Action.EVENTS_MANAGE))]


async def get_event_or_404(db: AsyncSession, event_id: UUID) -> EventDB:
    result = await db.execute(select(EventDB).where(EventDB.id == event_id))
    event = result.scalar_one_or_none()
    if event is None:
        raise HTTPException(status_code=404, detail="Event not found")
    return event
