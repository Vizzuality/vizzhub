"""Devstack API dependencies."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import TokenData
from app.core.permissions import Action, require_permission
from app.modules.devstack.models.entry import DevstackEntryDB

DevstackViewer = Annotated[TokenData, Depends(require_permission(Action.DEVSTACK_VIEW))]
DevstackManager = Annotated[TokenData, Depends(require_permission(Action.DEVSTACK_MANAGE))]


async def get_entry_or_404(db: AsyncSession, entry_id: UUID) -> DevstackEntryDB:
    result = await db.execute(select(DevstackEntryDB).where(DevstackEntryDB.id == entry_id))
    entry = result.scalar_one_or_none()
    if entry is None:
        raise HTTPException(status_code=404, detail="Devstack entry not found")
    return entry
