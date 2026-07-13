"""Human-readable summary generation for command queue entries.

Called at enqueue time to produce descriptions like
"Create page **Data Retention Policy** in Policies" instead of raw IDs.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.program import ProgramDB
from app.core.services.content_version_service import ContentVersionService
from app.modules.iso_docs.models.node import IsoDocNodeDB
from app.modules.iso_docs.models.page_version import IsoDocVersionDB
from app.modules.playbook.models.node import PlaybookNodeDB
from app.modules.playbook.models.page_version import PlaybookPageVersionDB

from mcp_server.handlers._shared import get_node_title

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
        parent_title = await get_node_title(session, IsoDocNodeDB, target)
    return f"Create page **{title}** in {parent_title}"


async def _iso_update_page_content(
    session: AsyncSession, target: str | None, payload: dict,
) -> str:
    node_title = target or "unknown"
    current_version = 0
    if target:
        result = await session.execute(
            select(IsoDocNodeDB).where(IsoDocNodeDB.slug == target)
        )
        node = result.scalar_one_or_none()
        if node:
            node_title = node.title
            latest = await _iso_versions.get_latest(session, node.id)
            if latest:
                current_version = latest.version
    next_version = current_version + 1
    return f"Update content of **{node_title}** (v{current_version} \u2192 v{next_version})"


async def _iso_patch_page_content(
    session: AsyncSession, target: str | None, payload: dict,
) -> str:
    node_title = target or "unknown"
    current_version = 0
    if target:
        result = await session.execute(
            select(IsoDocNodeDB).where(IsoDocNodeDB.slug == target)
        )
        node = result.scalar_one_or_none()
        if node:
            node_title = node.title
            latest = await _iso_versions.get_latest(session, node.id)
            if latest:
                current_version = latest.version
    next_version = current_version + 1
    ops = payload.get("operations", [])
    descriptions: list[str] = []
    for op in ops:
        desc = op.get("description")
        if not desc:
            search = op.get("search", "")
            desc = f"replace '{search[:30]}...'" if len(search) > 30 else f"replace '{search}'"
        descriptions.append(desc)
    ops_summary = _field_list(descriptions)
    return (
        f"Patch **{node_title}** (v{current_version} → v{next_version}): "
        f"{ops_summary}"
    )


async def _iso_update_metadata(
    session: AsyncSession, target: str | None, payload: dict,
) -> str:
    node_title = target or "unknown"
    if target:
        node_title = await get_node_title(session, IsoDocNodeDB, target)
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
        node_title = await get_node_title(session, IsoDocNodeDB, target)

    parts: list[str] = []
    if "title" in payload:
        parts.append(f"Rename **{node_title}** \u2192 **{payload['title']}**")
    if "parent_slug" in payload:
        parent_slug = payload["parent_slug"]
        parent_name = await get_node_title(session, IsoDocNodeDB, parent_slug)
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
        node_title = await get_node_title(session, IsoDocNodeDB, target)
    return f"Delete **{node_title}**"


async def _iso_create_registry_row(
    session: AsyncSession, target: str | None, payload: dict,
) -> str:
    registry_name = target or "unknown"
    if target:
        registry_name = await get_node_title(session, IsoDocNodeDB, target)
    data = payload.get("data", {})
    if data:
        return f"Create row in **{registry_name}**: {_key_value_preview(data)}"
    return f"Create row in **{registry_name}**"


async def _iso_update_registry_row(
    session: AsyncSession, target: str | None, payload: dict,
) -> str:
    registry_name = target or "unknown"
    if target:
        registry_name = await get_node_title(session, IsoDocNodeDB, target)
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
        registry_name = await get_node_title(session, IsoDocNodeDB, target)
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
        parent_title = await get_node_title(session, PlaybookNodeDB, target)
    return f"Create article **{title}** in {parent_title}"


async def _playbook_update_article_content(
    session: AsyncSession, target: str | None, payload: dict,
) -> str:
    node_title = target or "unknown"
    current_version = 0
    if target:
        result = await session.execute(
            select(PlaybookNodeDB).where(PlaybookNodeDB.slug == target)
        )
        node = result.scalar_one_or_none()
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
        node_title = await get_node_title(session, PlaybookNodeDB, target)

    parts: list[str] = []
    if "title" in payload:
        parts.append(f"Rename **{node_title}** \u2192 **{payload['title']}**")
    if "parent_slug" in payload:
        parent_slug = payload["parent_slug"]
        parent_name = await get_node_title(session, PlaybookNodeDB, parent_slug)
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
        node_title = await get_node_title(session, PlaybookNodeDB, target)
    return f"Delete **{node_title}**"


# ---------------------------------------------------------------------------
# Portfolio generators
# ---------------------------------------------------------------------------

async def _portfolio_program_name(session: AsyncSession, target: str | None) -> str:
    if not target:
        return "unknown"
    try:
        program_id = UUID(target)
    except ValueError:
        return target
    result = await session.execute(select(ProgramDB).where(ProgramDB.id == program_id))
    program = result.scalar_one_or_none()
    return program.name if program else target


async def _portfolio_create_program(
    session: AsyncSession, target: str | None, payload: dict,
) -> str:
    return f"Create program **{payload.get('name', 'untitled')}**"


async def _portfolio_rename_program(
    session: AsyncSession, target: str | None, payload: dict,
) -> str:
    old_name = await _portfolio_program_name(session, target)
    return f"Rename program **{old_name}** → **{payload.get('name', 'untitled')}**"


async def _portfolio_update_profile(
    session: AsyncSession, target: str | None, payload: dict,
) -> str:
    program_name = await _portfolio_program_name(session, target)
    parts = [
        f"clear {field}" if isinstance(value, str) and not value.strip() else field
        for field, value in payload.items()
    ]
    return f"Update profile of **{program_name}** ({', '.join(sorted(parts))})"


async def _portfolio_set_tags(
    session: AsyncSession, target: str | None, payload: dict,
) -> str:
    program_name = await _portfolio_program_name(session, target)
    taxonomy = payload.get("taxonomy", "unknown")
    names = payload.get("term_names") or []
    terms = ", ".join(names) if names else "none (clear)"
    summary = f"Set {taxonomy} tags of **{program_name}** → {terms}"
    if payload.get("primary"):
        summary += f" (primary: {payload['primary']})"
    return summary


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------

_GENERATORS: dict[tuple[str, str], Generator] = {
    ("iso_docs", "create_page"): _iso_create_page,
    ("iso_docs", "update_page_content"): _iso_update_page_content,
    ("iso_docs", "patch_page_content"): _iso_patch_page_content,
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
    ("portfolio", "create_program"): _portfolio_create_program,
    ("portfolio", "rename_program"): _portfolio_rename_program,
    ("portfolio", "update_profile"): _portfolio_update_profile,
    ("portfolio", "set_tags"): _portfolio_set_tags,
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
