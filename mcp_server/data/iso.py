"""ISO data access — registry types, rows, documents, search."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.iso_docs.models import RegistryTypeDB


async def get_registry_types(session: AsyncSession) -> list[RegistryTypeDB]:
    """Return all registry types ordered by name."""
    result = await session.execute(
        select(RegistryTypeDB).order_by(RegistryTypeDB.name)
    )
    return list(result.scalars().all())
