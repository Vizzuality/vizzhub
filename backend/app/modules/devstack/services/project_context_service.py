"""CRUD service for DevstackProjectContextDB.

Domain rules:
- slug is globally unique and immutable after creation.
- project_id is NOT NULL and each project may have at most one context.
- Only `description` is editable via update().
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.devstack.models.project_context import DevstackProjectContextDB


class DuplicateSlugError(Exception):
    """Raised when attempting to create a context with an already-used slug."""


class ProjectAlreadyLinkedError(Exception):
    """Raised when the target project already has a linked context."""


class SlugImmutableError(Exception):
    """Raised when an update attempts to change slug or project_id."""


class DevstackProjectContextService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def list(self) -> list[DevstackProjectContextDB]:
        result = await self.db.execute(
            select(DevstackProjectContextDB).order_by(DevstackProjectContextDB.slug)
        )
        return list(result.scalars().all())

    async def get(self, context_id: UUID) -> DevstackProjectContextDB | None:
        return await self.db.get(DevstackProjectContextDB, context_id)

    async def get_by_slug(self, slug: str) -> DevstackProjectContextDB | None:
        result = await self.db.execute(
            select(DevstackProjectContextDB).where(
                DevstackProjectContextDB.slug == slug
            )
        )
        return result.scalar_one_or_none()

    async def create(
        self,
        *,
        slug: str,
        project_id: UUID,
        description: str | None,
    ) -> DevstackProjectContextDB:
        if await self.get_by_slug(slug) is not None:
            raise DuplicateSlugError(slug)

        existing = await self.db.execute(
            select(DevstackProjectContextDB).where(
                DevstackProjectContextDB.project_id == project_id
            )
        )
        if existing.scalar_one_or_none() is not None:
            raise ProjectAlreadyLinkedError(project_id)

        ctx = DevstackProjectContextDB(
            slug=slug,
            project_id=project_id,
            description=description,
        )
        self.db.add(ctx)
        await self.db.flush()
        return ctx

    async def update(
        self,
        context_id: UUID,
        *,
        description: str | None = None,
        slug: str | None = None,
        project_id: UUID | None = None,
    ) -> DevstackProjectContextDB:
        if slug is not None or project_id is not None:
            raise SlugImmutableError("slug and project_id are immutable after creation")

        ctx = await self.db.get(DevstackProjectContextDB, context_id)
        if ctx is None:
            raise KeyError(context_id)

        ctx.description = description
        await self.db.flush()
        return ctx

    async def delete(self, context_id: UUID) -> None:
        ctx = await self.db.get(DevstackProjectContextDB, context_id)
        if ctx is not None:
            await self.db.delete(ctx)
            await self.db.flush()
