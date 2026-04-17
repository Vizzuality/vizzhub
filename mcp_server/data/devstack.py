"""DevStack data access — catalog entries and sync status."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.devstack.models.entry import DevstackEntryDB
from app.modules.devstack.models.user_pref import DevstackUserPrefDB


async def get_catalog_for_user(session: AsyncSession, user_id: str) -> list[dict]:
    """Return the user's active devstack catalog.

    Includes all entries where required=True, plus any optional entries
    the user has explicitly opted into (pref exists with enabled=True).
    """
    entries_stmt = select(DevstackEntryDB).where(DevstackEntryDB.active.is_(True))
    entries_result = await session.execute(entries_stmt)
    entries = entries_result.scalars().all()

    if not entries:
        return []

    entry_ids = [e.id for e in entries]
    prefs_stmt = select(DevstackUserPrefDB).where(
        DevstackUserPrefDB.user_id == UUID(user_id),
        DevstackUserPrefDB.entry_id.in_(entry_ids),
    )
    prefs_result = await session.execute(prefs_stmt)
    prefs_by_entry: dict[UUID, DevstackUserPrefDB] = {
        p.entry_id: p for p in prefs_result.scalars().all()
    }

    catalog = []
    for entry in entries:
        pref = prefs_by_entry.get(entry.id)
        opted_in = pref is not None and pref.enabled
        if not entry.required and not opted_in:
            continue
        catalog.append({
            "name": entry.name,
            "description": entry.description,
            "type": entry.type,
            "install_method": entry.install_method,
            "url": entry.url,
            "package": entry.package,
            "package_version": entry.package_version,
            "origin": entry.origin,
            "tech": entry.tech,
            "last_synced_sha": pref.last_synced_sha if pref else None,
        })
    return catalog


async def update_sync_status(
    session: AsyncSession,
    user_id: str,
    entry_name: str,
    sha: str,
) -> bool:
    """Update the last_synced_sha for a user's devstack entry.

    Creates a user pref record if one does not exist yet.
    Returns True if the entry was found, False otherwise.
    """
    entry_result = await session.execute(
        select(DevstackEntryDB).where(DevstackEntryDB.name == entry_name)
    )
    entry = entry_result.scalar_one_or_none()
    if entry is None:
        return False

    pref_result = await session.execute(
        select(DevstackUserPrefDB).where(
            DevstackUserPrefDB.user_id == UUID(user_id),
            DevstackUserPrefDB.entry_id == entry.id,
        )
    )
    pref = pref_result.scalar_one_or_none()

    if pref is None:
        pref = DevstackUserPrefDB(
            user_id=UUID(user_id),
            entry_id=entry.id,
            enabled=entry.required,
        )
        session.add(pref)

    pref.last_synced_sha = sha
    pref.last_synced_at = datetime.now(timezone.utc)
    return True
