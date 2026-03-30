"""Tree operations for playbook nodes."""

from __future__ import annotations

import re
import unicodedata
from uuid import UUID

from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.playbook.models.node import PlaybookNodeDB

MAX_DEPTH = 10


def generate_slug(title: str) -> str:
    """Convert title to URL-friendly slug."""
    normalized = unicodedata.normalize("NFKD", title)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    # Remove apostrophes/quotes before word boundaries so "what's" → "whats"
    no_quotes = re.sub(r"['\"]", "", ascii_text)
    lowered = no_quotes.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    return slug or "untitled"


async def ensure_unique_slug(
    db: AsyncSession,
    slug: str,
    parent_id: UUID | None,
    exclude_id: UUID | None = None,
) -> str:
    """Append -2, -3, etc. if slug already exists under the same parent."""
    base_slug = slug
    counter = 1
    while True:
        conditions = [
            PlaybookNodeDB.slug == slug,
            PlaybookNodeDB.parent_id == parent_id
            if parent_id
            else PlaybookNodeDB.parent_id.is_(None),
        ]
        if exclude_id is not None:
            conditions.append(PlaybookNodeDB.id != exclude_id)
        result = await db.execute(
            select(sa_func.count()).select_from(PlaybookNodeDB).where(*conditions)
        )
        if result.scalar_one() == 0:
            return slug
        counter += 1
        slug = f"{base_slug}-{counter}"


async def get_next_position(db: AsyncSession, parent_id: UUID | None) -> int:
    """Return next position for a new sibling under parent_id."""
    condition = (
        PlaybookNodeDB.parent_id == parent_id
        if parent_id
        else PlaybookNodeDB.parent_id.is_(None)
    )
    result = await db.execute(
        select(sa_func.coalesce(sa_func.max(PlaybookNodeDB.position), -1)).where(
            condition
        )
    )
    return result.scalar_one() + 1


async def validate_depth(db: AsyncSession, parent_id: UUID | None) -> bool:
    """Check that adding a child under parent_id won't exceed MAX_DEPTH."""
    if parent_id is None:
        return True
    depth = 1
    current_id = parent_id
    while current_id is not None:
        result = await db.execute(
            select(PlaybookNodeDB.parent_id).where(PlaybookNodeDB.id == current_id)
        )
        row = result.one_or_none()
        if row is None:
            break
        current_id = row[0]
        depth += 1
        if depth > MAX_DEPTH:
            return False
    return True


async def validate_not_circular(
    db: AsyncSession, node_id: UUID, new_parent_id: UUID | None
) -> bool:
    """Ensure new_parent_id is not a descendant of node_id."""
    if new_parent_id is None:
        return True
    current_id = new_parent_id
    while current_id is not None:
        if current_id == node_id:
            return False
        result = await db.execute(
            select(PlaybookNodeDB.parent_id).where(PlaybookNodeDB.id == current_id)
        )
        row = result.one_or_none()
        if row is None:
            break
        current_id = row[0]
    return True
