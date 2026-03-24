"""Generic content versioning service.

Parameterized by SQLAlchemy model class. Each module provides its own
version table but shares this logic. Used by playbook now, ISO later.
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession


class ContentVersionService:
    """Append-only version store for any entity with text content."""

    def __init__(self, model_class: type, entity_fk_field: str) -> None:
        self._model = model_class
        self._fk_field = entity_fk_field

    def _fk_col(self):
        return getattr(self._model, self._fk_field)

    async def save_version(
        self,
        db: AsyncSession,
        entity_id: UUID,
        content: str,
        user_id: UUID | None,
    ) -> int:
        """Create a new version. Returns the version number."""
        result = await db.execute(
            select(sa_func.coalesce(sa_func.max(self._model.version), 0)).where(
                self._fk_col() == entity_id
            )
        )
        next_version = result.scalar_one() + 1

        record = self._model(
            **{
                self._fk_field: entity_id,
                "content": content,
                "version": next_version,
                "created_by_id": user_id,
            }
        )
        db.add(record)
        await db.flush()
        return next_version

    async def get_latest(self, db: AsyncSession, entity_id: UUID):
        """Return the latest version record, or None."""
        result = await db.execute(
            select(self._model)
            .where(self._fk_col() == entity_id)
            .order_by(self._model.version.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_version(self, db: AsyncSession, entity_id: UUID, version: int):
        """Return a specific version record, or None."""
        result = await db.execute(
            select(self._model).where(
                self._fk_col() == entity_id,
                self._model.version == version,
            )
        )
        return result.scalar_one_or_none()

    async def list_versions(self, db: AsyncSession, entity_id: UUID) -> list:
        """Return all versions, newest first."""
        result = await db.execute(
            select(self._model)
            .where(self._fk_col() == entity_id)
            .order_by(self._model.version.desc())
        )
        return list(result.scalars().all())
