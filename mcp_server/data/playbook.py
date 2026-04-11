"""Playbook data access — tree, articles, search."""

from __future__ import annotations

from sqlalchemy import and_, func as sa_func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.playbook.models.node import PlaybookNodeDB
from app.modules.playbook.models.page_version import PlaybookPageVersionDB


_SUMMARY_LENGTH = 200

_latest_version_sq = (
    select(
        PlaybookPageVersionDB.node_id,
        sa_func.max(PlaybookPageVersionDB.version).label("max_version"),
    )
    .group_by(PlaybookPageVersionDB.node_id)
    .subquery()
)


def _build_tree(nodes: list[PlaybookNodeDB]) -> list[dict]:
    """Build hierarchical tree from flat list of nodes."""
    node_map: dict = {}
    roots: list[dict] = []

    for n in nodes:
        node_map[n.id] = {
            "id": str(n.id),
            "title": n.title,
            "slug": n.slug,
            "type": n.type,
            "is_public": n.is_public,
            "children": [],
        }

    for n in nodes:
        entry = node_map[n.id]
        if n.parent_id and n.parent_id in node_map:
            node_map[n.parent_id]["children"].append(entry)
        else:
            roots.append(entry)

    return roots


async def get_tree(session: AsyncSession) -> list[dict]:
    """Hierarchical tree of all playbook nodes."""
    result = await session.execute(
        select(PlaybookNodeDB).order_by(PlaybookNodeDB.position)
    )
    nodes = list(result.scalars().all())
    return _build_tree(nodes)


async def get_article(session: AsyncSession, slug: str) -> dict | None:
    """Full article content by slug."""
    stmt = (
        select(
            PlaybookNodeDB.id,
            PlaybookNodeDB.title,
            PlaybookNodeDB.slug,
            PlaybookNodeDB.is_public,
            PlaybookPageVersionDB.content,
            PlaybookPageVersionDB.version,
            PlaybookPageVersionDB.created_at,
        )
        .join(
            _latest_version_sq,
            _latest_version_sq.c.node_id == PlaybookNodeDB.id,
        )
        .join(
            PlaybookPageVersionDB,
            and_(
                PlaybookPageVersionDB.node_id == PlaybookNodeDB.id,
                PlaybookPageVersionDB.version == _latest_version_sq.c.max_version,
            ),
        )
        .where(PlaybookNodeDB.slug == slug)
        .where(PlaybookNodeDB.type == "page")
    )

    result = await session.execute(stmt)
    row = result.first()
    if row is None:
        return None

    return {
        "id": str(row.id),
        "title": row.title,
        "slug": row.slug,
        "is_public": row.is_public,
        "content": row.content,
        "version": row.version,
        "last_updated": row.created_at,
    }


async def search_articles(session: AsyncSession, query: str) -> list[dict]:
    """Search playbook articles by title and content (ILIKE)."""
    pattern = f"%{query}%"

    stmt = (
        select(
            PlaybookNodeDB.id,
            PlaybookNodeDB.title,
            PlaybookNodeDB.slug,
            PlaybookNodeDB.is_public,
            sa_func.left(PlaybookPageVersionDB.content, _SUMMARY_LENGTH).label("summary"),
        )
        .join(
            _latest_version_sq,
            _latest_version_sq.c.node_id == PlaybookNodeDB.id,
        )
        .join(
            PlaybookPageVersionDB,
            and_(
                PlaybookPageVersionDB.node_id == PlaybookNodeDB.id,
                PlaybookPageVersionDB.version == _latest_version_sq.c.max_version,
            ),
        )
        .where(PlaybookNodeDB.type == "page")
        .where(
            PlaybookNodeDB.title.ilike(pattern)
            | PlaybookPageVersionDB.content.ilike(pattern)
        )
        .order_by(PlaybookNodeDB.title)
    )

    result = await session.execute(stmt)
    return [
        {
            "id": str(row.id),
            "title": row.title,
            "slug": row.slug,
            "is_public": row.is_public,
            "summary": row.summary,
        }
        for row in result.all()
    ]
