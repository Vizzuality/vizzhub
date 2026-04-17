"""DevStack data access — catalog entries."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.devstack.models.entry import DevstackEntryDB
from app.modules.devstack.schemas import EntryResponse

_CATALOG_FIELDS = ("name", "description", "type", "install_method", "url", "package", "package_version", "origin", "tech")


async def get_catalog(session: AsyncSession) -> list[dict]:
    """Return all active devstack catalog entries."""
    result = await session.execute(
        select(DevstackEntryDB).where(DevstackEntryDB.active.is_(True))
    )
    entries = result.scalars().all()
    return [
        EntryResponse.model_validate(entry).model_dump(include=set(_CATALOG_FIELDS))
        for entry in entries
    ]
