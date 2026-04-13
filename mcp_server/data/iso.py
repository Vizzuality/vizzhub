"""ISO data access — registry types, rows, documents, search."""

from __future__ import annotations

import re
from uuid import UUID

from sqlalchemy import and_, func as sa_func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased
from sqlalchemy.sql import Select

from app.core.models.user import UserDB
from app.modules.iso_docs.models import (
    IsoDocMetadataDB,
    IsoDocNodeDB,
    IsoDocNoteDB,
    IsoDocVersionDB,
    RegistryRowDB,
    RegistryTypeDB,
)
from mcp_server.data.base import get_mcp_user


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

# Aliased parent node for deriving category from tree structure.
_ParentNode = aliased(IsoDocNodeDB)

# Root group slugs visible to non-editors. Mirrors backend's
# USER_VISIBLE_ROOT_SLUGS in app/modules/iso_docs/api/deps.py.
_USER_VISIBLE_ROOT_SLUGS = {"policies", "procedures"}


async def _get_visible_node_ids(session: AsyncSession) -> set[UUID] | None:
    """Return IDs of nodes visible to the current user, or None if no filter needed."""
    try:
        user = get_mcp_user()
    except RuntimeError:
        return None
    if user.has_permission("iso_docs:edit"):
        return None

    result = await session.execute(
        text("""
            WITH RECURSIVE visible_tree AS (
                SELECT id FROM iso_doc_nodes
                WHERE slug = ANY(:slugs) AND parent_id IS NULL
                UNION ALL
                SELECT n.id FROM iso_doc_nodes n
                INNER JOIN visible_tree vt ON n.parent_id = vt.id
            )
            SELECT id FROM visible_tree
        """),
        {"slugs": list(_USER_VISIBLE_ROOT_SLUGS)},
    )
    return {row[0] for row in result.all()}


def _doc_base_query(*extra_columns) -> Select:
    """Build the common SELECT + JOIN chain for document queries.

    Joins iso_doc_nodes -> parent node -> metadata -> latest version -> version.
    Category is derived from the parent group's title (matching the backend API),
    not from the metadata enum field.
    """
    return (
        select(
            IsoDocNodeDB.slug,
            IsoDocNodeDB.title,
            _ParentNode.title.label("category"),
            IsoDocMetadataDB.doc_version,
            *extra_columns,
        )
        .outerjoin(_ParentNode, _ParentNode.id == IsoDocNodeDB.parent_id)
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
    )


async def get_documents(
    session: AsyncSession,
    category: str | None = None,
    title_search: str | None = None,
) -> list[dict]:
    """Return ISO documents (page nodes) with metadata and content summary."""
    visible_ids = await _get_visible_node_ids(session)

    stmt = _doc_base_query(
        IsoDocVersionDB.created_at.label("last_updated"),
        sa_func.left(IsoDocVersionDB.content, _SUMMARY_LENGTH).label("summary"),
    ).order_by(IsoDocNodeDB.title)

    if visible_ids is not None:
        stmt = stmt.where(IsoDocNodeDB.id.in_(visible_ids))
    if category is not None:
        stmt = stmt.where(_ParentNode.title == category)
    if title_search is not None:
        stmt = stmt.where(IsoDocNodeDB.title.ilike(f"%{title_search}%"))

    result = await session.execute(stmt)
    return [row._asdict() for row in result.all()]


async def get_document(session: AsyncSession, slug: str) -> dict:
    """Return full content of a single ISO document by slug.

    Raises ValueError if slug not found or not visible to current user.
    """
    visible_ids = await _get_visible_node_ids(session)

    stmt = _doc_base_query(
        IsoDocVersionDB.content,
    ).where(IsoDocNodeDB.slug == slug)

    if visible_ids is not None:
        stmt = stmt.where(IsoDocNodeDB.id.in_(visible_ids))

    result = await session.execute(stmt)
    row = result.first()
    if row is None:
        raise ValueError(f"Document '{slug}' not found")
    return row._asdict()


def _extract_section_heading(content: str, snippet: str) -> str | None:
    """Find the nearest preceding markdown heading for the highlighted match.

    Extracts the first highlighted term from the snippet, locates it in the
    full content, then walks backwards to find the nearest ## heading.
    Returns None if no heading is found before the match position.
    """
    # Extract the first highlighted term to pinpoint match position in content
    highlighted = re.search(r"<b>(.+?)</b>", snippet)
    if highlighted:
        search_term = highlighted.group(1)
        pos = content.find(search_term)
    else:
        # Fallback: search for the beginning of the cleaned snippet
        clean_snippet = re.sub(r"<b>|</b>", "", snippet).strip()
        fragment = clean_snippet[:60]
        pos = content.find(fragment)

    if pos < 0:
        return None
    preceding = content[:pos]
    headings = [
        line for line in preceding.split("\n")
        if line.startswith("#")
        and not line.startswith("####")
        and len(line) > len(line.split()[0])
    ]
    return headings[-1] if headings else None


async def search_documents(
    session: AsyncSession, query: str,
) -> list[dict]:
    """Full-text search across ISO document content.

    Respects user visibility: non-editors only see results from
    documents under policies and procedures root groups.
    """
    visible_ids = await _get_visible_node_ids(session)

    visibility_filter = ""
    params: dict = {"query": query}
    if visible_ids is not None:
        visibility_filter = "AND n.id = ANY(:visible_ids)"
        params["visible_ids"] = list(visible_ids)

    stmt = text(f"""
        WITH latest_versions AS (
            SELECT DISTINCT ON (v.node_id)
                v.node_id, v.content, v.search_vector, v.version
            FROM iso_doc_versions v
            ORDER BY v.node_id, v.version DESC
        )
        SELECT
            n.slug,
            n.title,
            lv.content,
            ts_headline('english', lv.content, plainto_tsquery('english', :query),
                'StartSel=<b>, StopSel=</b>, MaxWords=50, MinWords=20'
            ) AS snippet,
            ts_rank(lv.search_vector, plainto_tsquery('english', :query)) AS rank
        FROM latest_versions lv
        JOIN iso_doc_nodes n ON n.id = lv.node_id
        WHERE n.type = 'page'
          AND lv.search_vector @@ plainto_tsquery('english', :query)
          {visibility_filter}
        ORDER BY rank DESC
    """)
    result = await session.execute(stmt, params)
    rows = result.all()
    return [
        {
            "slug": row.slug,
            "title": row.title,
            "section": _extract_section_heading(row.content, row.snippet),
            "snippet": row.snippet,
            "rank": float(row.rank),
        }
        for row in rows
    ]


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


def _user_display_name_expr(user_alias):
    """SQL expression resolving to first+last > name > email for a user alias."""
    return sa_func.coalesce(
        sa_func.nullif(
            sa_func.concat_ws(
                " ",
                sa_func.nullif(user_alias.first_name, ""),
                sa_func.nullif(user_alias.last_name, ""),
            ),
            "",
        ),
        user_alias.name,
        user_alias.email,
    )


def _note_row_to_dict(note: IsoDocNoteDB, creator_name, doner_name) -> dict:
    return {
        "id": str(note.id),
        "content": note.content,
        "done": note.done,
        "done_at": note.done_at,
        "done_by": doner_name,
        "created_by": creator_name,
        "created_at": note.created_at,
        "updated_at": note.updated_at,
    }


async def get_node_notes(
    session: AsyncSession, slug: str, include_done: bool,
) -> dict:
    """Return notes attached to a node identified by slug.

    Raises ValueError if the slug does not match any ISO doc node.
    """
    node_row = (await session.execute(
        select(IsoDocNodeDB).where(IsoDocNodeDB.slug == slug)
    )).scalar_one_or_none()
    if node_row is None:
        raise ValueError(f"Node '{slug}' not found")

    creator_alias = aliased(UserDB)
    doner_alias = aliased(UserDB)
    stmt = (
        select(
            IsoDocNoteDB,
            _user_display_name_expr(creator_alias),
            _user_display_name_expr(doner_alias),
        )
        .outerjoin(creator_alias, creator_alias.id == IsoDocNoteDB.created_by_id)
        .outerjoin(doner_alias, doner_alias.id == IsoDocNoteDB.done_by_id)
        .where(IsoDocNoteDB.node_id == node_row.id)
        .order_by(IsoDocNoteDB.done.asc(), IsoDocNoteDB.created_at.desc())
    )
    if not include_done:
        stmt = stmt.where(IsoDocNoteDB.done.is_(False))

    rows = (await session.execute(stmt)).all()
    return {
        "node_slug": node_row.slug,
        "node_title": node_row.title,
        "node_type": node_row.type,
        "total_notes": len(rows),
        "notes": [_note_row_to_dict(*row) for row in rows],
    }


async def get_pending_notes(session: AsyncSession) -> list[dict]:
    """Return all pending (not done) notes across all ISO nodes.

    Each entry includes the node's slug, title and type so the caller
    can group or link back to the source node.
    """
    creator_alias = aliased(UserDB)
    stmt = (
        select(
            IsoDocNoteDB,
            IsoDocNodeDB.slug.label("node_slug"),
            IsoDocNodeDB.title.label("node_title"),
            IsoDocNodeDB.type.label("node_type"),
            _user_display_name_expr(creator_alias),
        )
        .join(IsoDocNodeDB, IsoDocNodeDB.id == IsoDocNoteDB.node_id)
        .outerjoin(creator_alias, creator_alias.id == IsoDocNoteDB.created_by_id)
        .where(IsoDocNoteDB.done.is_(False))
        .order_by(IsoDocNodeDB.title.asc(), IsoDocNoteDB.created_at.desc())
    )
    rows = (await session.execute(stmt)).all()
    return [
        {
            "id": str(note.id),
            "node_slug": node_slug,
            "node_title": node_title,
            "node_type": node_type,
            "content": note.content,
            "created_by": creator_name,
            "created_at": note.created_at,
        }
        for note, node_slug, node_title, node_type, creator_name in rows
    ]
