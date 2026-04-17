"""DevStack data access — catalog entries."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.devstack.models.entry import DevstackEntryDB


async def get_catalog(session: AsyncSession) -> list[dict]:
    """Return all active devstack catalog entries."""
    result = await session.execute(
        select(DevstackEntryDB).where(DevstackEntryDB.active.is_(True))
    )
    entries = result.scalars().all()

    return [
        {
            "name": entry.name,
            "description": entry.description,
            "type": entry.type,
            "install_method": entry.install_method,
            "url": entry.url,
            "package": entry.package,
            "package_version": entry.package_version,
            "origin": entry.origin,
            "tech": entry.tech,
        }
        for entry in entries
    ]
