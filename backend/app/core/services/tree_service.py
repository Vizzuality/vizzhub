"""Generic tree operations for hierarchical node models.

Parameterized by SQLAlchemy model class. Each module provides its own
node table but shares this logic. Used by playbook and iso_docs.
"""

from __future__ import annotations

import re
import unicodedata
from uuid import UUID

from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession

MAX_DEPTH = 10


def generate_slug(title: str) -> str:
    """Convert title to URL-friendly slug."""
    normalized = unicodedata.normalize("NFKD", title)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    no_quotes = re.sub(r"['\"]", "", ascii_text)
    lowered = no_quotes.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", lowered).strip("-")
    return slug or "untitled"


class TreeService:
    """Reusable tree operations for any self-referential node model."""

    def __init__(self, model_class: type) -> None:
        self._model = model_class

    async def ensure_unique_slug(
        self,
        db: AsyncSession,
        slug: str,
        exclude_id: UUID | None = None,
    ) -> str:
        """Append -2, -3, etc. if slug already exists globally."""
        base_slug = slug
        counter = 1
        while True:
            conditions = [self._model.slug == slug]
            if exclude_id is not None:
                conditions.append(self._model.id != exclude_id)
            result = await db.execute(
                select(sa_func.count()).select_from(self._model).where(*conditions)
            )
            if result.scalar_one() == 0:
                return slug
            counter += 1
            slug = f"{base_slug}-{counter}"

    async def get_next_position(
        self, db: AsyncSession, parent_id: UUID | None
    ) -> int:
        """Return next position for a new sibling under parent_id."""
        condition = (
            self._model.parent_id == parent_id
            if parent_id
            else self._model.parent_id.is_(None)
        )
        result = await db.execute(
            select(
                sa_func.coalesce(sa_func.max(self._model.position), -1)
            ).where(condition)
        )
        return result.scalar_one() + 1

    async def validate_depth(
        self, db: AsyncSession, parent_id: UUID | None
    ) -> bool:
        """Check that adding a child under parent_id won't exceed MAX_DEPTH."""
        if parent_id is None:
            return True
        depth = 1
        current_id = parent_id
        while current_id is not None:
            result = await db.execute(
                select(self._model.parent_id).where(
                    self._model.id == current_id
                )
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
        self, db: AsyncSession, node_id: UUID, new_parent_id: UUID | None
    ) -> bool:
        """Ensure new_parent_id is not a descendant of node_id."""
        if new_parent_id is None:
            return True
        current_id = new_parent_id
        while current_id is not None:
            if current_id == node_id:
                return False
            result = await db.execute(
                select(self._model.parent_id).where(
                    self._model.id == current_id
                )
            )
            row = result.one_or_none()
            if row is None:
                break
            current_id = row[0]
        return True
