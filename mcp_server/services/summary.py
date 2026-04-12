"""Human-readable summary generation for command queue entries.

Called at enqueue time to produce descriptions like
"Create page **Data Retention Policy** in Policies" instead of raw IDs.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.services.content_version_service import ContentVersionService
from app.modules.iso_docs.models.node import IsoDocNodeDB
from app.modules.iso_docs.models.page_version import IsoDocVersionDB
from app.modules.playbook.models.node import PlaybookNodeDB
from app.modules.playbook.models.page_version import PlaybookPageVersionDB

_iso_versions = ContentVersionService(
    model_class=IsoDocVersionDB,
    entity_fk_field="node_id",
)

_playbook_versions = ContentVersionService(
    model_class=PlaybookPageVersionDB,
    entity_fk_field="node_id",
)

Generator = Callable[
    [AsyncSession, str | None, dict],
    Awaitable[str],
]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_iso_node(session: AsyncSession, slug: str) -> IsoDocNodeDB | None:
    result = await session.execute(
        select(IsoDocNodeDB).where(IsoDocNodeDB.slug == slug)
    )
    return result.scalar_one_or_none()


async def _get_playbook_node(
    session: AsyncSession, slug: str,
) -> PlaybookNodeDB | None:
    result = await session.execute(
        select(PlaybookNodeDB).where(PlaybookNodeDB.slug == slug)
    )
    return result.scalar_one_or_none()


async def _iso_parent_title(session: AsyncSession, parent_id) -> str:
    if parent_id is None:
        return "root"
    result = await session.execute(
        select(IsoDocNodeDB.title).where(IsoDocNodeDB.id == parent_id)
    )
    title = result.scalar_one_or_none()
    return title or "unknown"


async def _playbook_parent_title(session: AsyncSession, parent_id) -> str:
    if parent_id is None:
        return "root"
    result = await session.execute(
        select(PlaybookNodeDB.title).where(PlaybookNodeDB.id == parent_id)
    )
    title = result.scalar_one_or_none()
    return title or "unknown"


def _field_list(fields: list[str], max_shown: int = 3) -> str:
    if len(fields) <= max_shown:
        return ", ".join(fields)
    shown = ", ".join(fields[:max_shown])
    return f"{shown} +{len(fields) - max_shown} more"


def _key_value_preview(data: dict, max_shown: int = 3) -> str:
    items = list(data.items())[:max_shown]
    parts = [f"{k}={v}" for k, v in items]
    preview = ", ".join(parts)
    if len(data) > max_shown:
        preview += f" +{len(data) - max_shown} more"
    return preview


# ---------------------------------------------------------------------------
# ISO Docs generators
# ---------------------------------------------------------------------------

async def _iso_create_page(
    session: AsyncSession, target: str | None, payload: dict,
) -> str:
    title = payload.get("title", "untitled")
    parent_title = "root"
    if target:
        parent = await _get_iso_node(session, target)
        if parent:
            parent_title = parent.title
    return f"Create page **{title}** in {parent_title}"


async def _iso_update_page_content(
    session: AsyncSession, target: str | None, payload: dict,
) -> str:
    node_title = target or "unknown"
    current_version = 0
    if target:
        node = await _get_iso_node(session, target)
        if node:
            node_title = node.title
            latest = await _iso_versions.get_latest(session, node.id)
            if latest:
                current_version = latest.version
    next_version = current_version + 1
    return f"Update content of **{node_title}** (v{current_version} \u2192 v{next_version})"


async def _iso_update_metadata(
    session: AsyncSession, target: str | None, payload: dict,
) -> str:
    node_title = target or "unknown"
    if target:
        node = await _get_iso_node(session, target)
        if node:
            node_title = node.title
    allowed_fields = {
        "code", "standard", "clauses", "classification", "status",
        "document_date", "original_filename", "guidance", "changelog",
    }
    fields = [k for k in payload if k in allowed_fields]
    if not fields:
        return f"Update metadata of **{node_title}**"
    return f"Update metadata of **{node_title}**: {_field_list(fields)}"


async def _iso_update_node(
    session: AsyncSession, target: str | None, payload: dict,
) -> str:
    node_title = target or "unknown"
    if target:
        node = await _get_iso_node(session, target)
        if node:
            node_title = node.title

    parts: list[str] = []
    if "title" in payload:
        parts.append(f"Rename **{node_title}** \u2192 **{payload['title']}**")
    if "parent_slug" in payload:
        parent_slug = payload["parent_slug"]
        parent = await _get_iso_node(session, parent_slug)
        parent_name = parent.title if parent else parent_slug
        move_target = payload.get("title", node_title)
        parts.append(f"Move **{move_target}** to {parent_name}")

    if not parts:
        return f"Update **{node_title}**"
    return "; ".join(parts)


async def _iso_delete_node(
    session: AsyncSession, target: str | None, payload: dict,
) -> str:
    node_title = target or "unknown"
    if target:
        node = await _get_iso_node(session, target)
        if node:
            node_title = node.title
    return f"Delete **{node_title}**"


async def _iso_create_registry_row(
    session: AsyncSession, target: str | None, payload: dict,
) -> str:
    registry_name = target or "unknown"
    if target:
        node = await _get_iso_node(session, target)
        if node:
            registry_name = node.title
    data = payload.get("data", {})
    if data:
        return f"Create row in **{registry_name}**: {_key_value_preview(data)}"
    return f"Create row in **{registry_name}**"


async def _iso_update_registry_row(
    session: AsyncSession, target: str | None, payload: dict,
) -> str:
    registry_name = target or "unknown"
    if target:
        node = await _get_iso_node(session, target)
        if node:
            registry_name = node.title
    data = payload.get("data", {})
    if data:
        fields = list(data.keys())
        return f"Update row in **{registry_name}**: {_field_list(fields)}"
    return f"Update row in **{registry_name}**"


async def _iso_delete_registry_row(
    session: AsyncSession, target: str | None, payload: dict,
) -> str:
    registry_name = target or "unknown"
    if target:
        node = await _get_iso_node(session, target)
        if node:
            registry_name = node.title
    return f"Delete row from **{registry_name}**"


# ---------------------------------------------------------------------------
# Playbook generators
# ---------------------------------------------------------------------------

async def _playbook_create_article(
    session: AsyncSession, target: str | None, payload: dict,
) -> str:
    title = payload.get("title", "untitled")
    parent_title = "root"
    if target:
        parent = await _get_playbook_node(session, target)
        if parent:
            parent_title = parent.title
    return f"Create article **{title}** in {parent_title}"


async def _playbook_update_article_content(
    session: AsyncSession, target: str | None, payload: dict,
) -> str:
    node_title = target or "unknown"
    current_version = 0
    if target:
        node = await _get_playbook_node(session, target)
        if node:
            node_title = node.title
            latest = await _playbook_versions.get_latest(session, node.id)
            if latest:
                current_version = latest.version
    next_version = current_version + 1
    return f"Update content of **{node_title}** (v{current_version} \u2192 v{next_version})"


async def _playbook_update_node(
    session: AsyncSession, target: str | None, payload: dict,
) -> str:
    node_title = target or "unknown"
    if target:
        node = await _get_playbook_node(session, target)
        if node:
            node_title = node.title

    parts: list[str] = []
    if "title" in payload:
        parts.append(f"Rename **{node_title}** \u2192 **{payload['title']}**")
    if "parent_slug" in payload:
        parent_slug = payload["parent_slug"]
        parent = await _get_playbook_node(session, parent_slug)
        parent_name = parent.title if parent else parent_slug
        move_target = payload.get("title", node_title)
        parts.append(f"Move **{move_target}** to {parent_name}")

    if not parts:
        return f"Update **{node_title}**"
    return "; ".join(parts)


async def _playbook_delete_node(
    session: AsyncSession, target: str | None, payload: dict,
) -> str:
    node_title = target or "unknown"
    if target:
        node = await _get_playbook_node(session, target)
        if node:
            node_title = node.title
    return f"Delete **{node_title}**"


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------

_GENERATORS: dict[tuple[str, str], Generator] = {
    ("iso_docs", "create_page"): _iso_create_page,
    ("iso_docs", "update_page_content"): _iso_update_page_content,
    ("iso_docs", "update_metadata"): _iso_update_metadata,
    ("iso_docs", "update_node"): _iso_update_node,
    ("iso_docs", "delete_node"): _iso_delete_node,
    ("iso_docs", "create_registry_row"): _iso_create_registry_row,
    ("iso_docs", "update_registry_row"): _iso_update_registry_row,
    ("iso_docs", "delete_registry_row"): _iso_delete_registry_row,
    ("playbook", "create_article"): _playbook_create_article,
    ("playbook", "update_article_content"): _playbook_update_article_content,
    ("playbook", "update_node"): _playbook_update_node,
    ("playbook", "delete_node"): _playbook_delete_node,
}


async def generate_summary(
    session: AsyncSession,
    module: str,
    action: str,
    target: str | None,
    payload: dict,
) -> str:
    """Generate a human-readable summary for a command queue entry."""
    generator = _GENERATORS.get((module, action))
    if generator is None:
        return f"{action} on {target or module}"
    return await generator(session, target, payload)
