"""ISO data access — registry types, rows, documents, search."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import and_, func as sa_func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.iso_docs.models import (
    IsoDocMetadataDB,
    IsoDocNodeDB,
    IsoDocVersionDB,
    RegistryRowDB,
    RegistryTypeDB,
)


# Subquery for latest version number per node
_latest_version_sq = (
    select(
        IsoDocVersionDB.node_id,
        sa_func.max(IsoDocVersionDB.version).label("max_version"),
    )
    .group_by(IsoDocVersionDB.node_id)
    .subquery()
)

_SUMMARY_LENGTH = 200


async def get_documents(
    session: AsyncSession,
    category: str | None = None,
    title_search: str | None = None,
) -> list[dict]:
    """Return ISO documents (page nodes) with metadata and content summary."""
    stmt = (
        select(
            IsoDocNodeDB.slug,
            IsoDocNodeDB.title,
            IsoDocMetadataDB.category,
            IsoDocMetadataDB.doc_version,
            IsoDocVersionDB.created_at.label("last_updated"),
            sa_func.left(IsoDocVersionDB.content, _SUMMARY_LENGTH).label("summary"),
        )
        .join(IsoDocMetadataDB, IsoDocMetadataDB.node_id == IsoDocNodeDB.id)
        .join(
            _latest_version_sq,
            _latest_version_sq.c.node_id == IsoDocNodeDB.id,
        )
        .join(
            IsoDocVersionDB,
            and_(
                IsoDocVersionDB.node_id == IsoDocNodeDB.id,
                IsoDocVersionDB.version == _latest_version_sq.c.max_version,
            ),
        )
        .where(IsoDocNodeDB.type == "page")
        .order_by(IsoDocNodeDB.title)
    )
    if category is not None:
        stmt = stmt.where(IsoDocMetadataDB.category == category)
    if title_search is not None:
        stmt = stmt.where(IsoDocNodeDB.title.ilike(f"%{title_search}%"))

    result = await session.execute(stmt)
    return [row._asdict() for row in result.all()]


async def get_document(session: AsyncSession, slug: str) -> dict:
    """Return full content of a single ISO document by slug.

    Raises ValueError if slug not found.
    """
    stmt = (
        select(
            IsoDocNodeDB.slug,
            IsoDocNodeDB.title,
            IsoDocMetadataDB.category,
            IsoDocMetadataDB.doc_version,
            IsoDocVersionDB.content,
        )
        .join(IsoDocMetadataDB, IsoDocMetadataDB.node_id == IsoDocNodeDB.id)
        .join(
            _latest_version_sq,
            _latest_version_sq.c.node_id == IsoDocNodeDB.id,
        )
        .join(
            IsoDocVersionDB,
            and_(
                IsoDocVersionDB.node_id == IsoDocNodeDB.id,
                IsoDocVersionDB.version == _latest_version_sq.c.max_version,
            ),
        )
        .where(IsoDocNodeDB.type == "page")
        .where(IsoDocNodeDB.slug == slug)
    )
    result = await session.execute(stmt)
    row = result.first()
    if row is None:
        raise ValueError(f"Document '{slug}' not found")
    return row._asdict()


async def get_registry_types(session: AsyncSession) -> list[RegistryTypeDB]:
    """Return all registry types ordered by name."""
    result = await session.execute(
        select(RegistryTypeDB).order_by(RegistryTypeDB.name)
    )
    return list(result.scalars().all())


async def resolve_registry_node(
    session: AsyncSession, slug: str,
) -> tuple[RegistryTypeDB, UUID]:
    """Resolve a registry type slug to (RegistryTypeDB, node_id).

    ISO registries live as nodes in the ISO document tree (iso_doc_nodes),
    each linked to a registry_type that defines the schema. This function
    encapsulates the JOIN between the two tables.

    Raises ValueError if the slug does not match any registry type or
    no node is linked to that registry type.
    """
    result = await session.execute(
        select(RegistryTypeDB, IsoDocNodeDB.id).join(
            IsoDocNodeDB,
            and_(
                IsoDocNodeDB.registry_type_id == RegistryTypeDB.id,
                IsoDocNodeDB.type == "registry",
            ),
        ).where(RegistryTypeDB.slug == slug)
    )
    row = result.first()
    if row is None:
        raise ValueError(f"Registry '{slug}' not found")
    return row[0], row[1]


async def get_registry_rows(
    session: AsyncSession, node_id: UUID, year: int | None,
) -> list[RegistryRowDB]:
    """Return registry rows for a node, optionally filtered by year."""
    stmt = (
        select(RegistryRowDB)
        .where(RegistryRowDB.node_id == node_id)
        .order_by(RegistryRowDB.row_index)
    )
    if year is not None:
        stmt = stmt.where(RegistryRowDB.year == year)
    result = await session.execute(stmt)
    return list(result.scalars().all())
