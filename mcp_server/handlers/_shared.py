"""Shared helpers for command handlers (iso_docs, playbook)."""

from uuid import UUID

from sqlalchemy import select, func as sa_func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase


def extract_h1(content: str) -> str | None:
    """Extract the first H1 title from markdown content."""
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("# "):
            return stripped[2:].strip()
        if stripped and not stripped.startswith("#"):
            break
    return None


async def resolve_node_by_slug[T: DeclarativeBase](
    session: AsyncSession,
    model: type[T],
    slug: str,
    *,
    expected_type: str | None = None,
) -> T:
    """Find a tree node by slug. Raises ValueError if not found or wrong type."""
    result = await session.execute(
        select(model).where(model.slug == slug)
    )
    node = result.scalar_one_or_none()
    if node is None:
        raise ValueError(f"Node with slug '{slug}' not found")
    if expected_type and node.type != expected_type:
        raise ValueError(
            f"Node '{slug}' is type '{node.type}', expected '{expected_type}'"
        )
    return node


async def delete_leaf_node[T: DeclarativeBase](
    session: AsyncSession,
    model: type[T],
    slug: str,
) -> None:
    """Delete a leaf node, raising ValueError if it has children."""
    node = await resolve_node_by_slug(session, model, slug)

    result = await session.execute(
        select(sa_func.count())
        .select_from(model)
        .where(model.parent_id == node.id)
    )
    child_count = result.scalar_one()
    if child_count > 0:
        raise ValueError(
            f"Node '{slug}' has children. Delete children first."
        )

    await session.delete(node)
    await session.flush()


async def update_node_tree[T: DeclarativeBase](
    session: AsyncSession,
    model: type[T],
    slug: str,
    payload: dict,
    user_id: UUID,
    *,
    tree_service,
) -> dict:
    """Rename and/or move a tree node. Returns serialized result dict."""
    node = await resolve_node_by_slug(session, model, slug)

    if "parent_slug" in payload:
        parent = await resolve_node_by_slug(
            session, model, payload["parent_slug"], expected_type="group",
        )
        if not await tree_service.validate_not_circular(session, node.id, parent.id):
            raise ValueError("Cannot move node under its own descendant")
        if not await tree_service.validate_depth(session, parent.id):
            raise ValueError("Maximum tree depth exceeded")
        node.parent_id = parent.id

    if "title" in payload:
        new_title = payload["title"]
        node.title = new_title
        node.slug = await tree_service.ensure_unique_slug(
            session, tree_service.generate_slug(new_title), exclude_id=node.id,
        )

    node.updated_by_id = user_id
    await session.flush()
    await session.refresh(node)

    return {
        "node_id": str(node.id),
        "slug": node.slug,
        "title": node.title,
        "parent_id": str(node.parent_id) if node.parent_id else None,
    }


async def get_node_title[T: DeclarativeBase](
    session: AsyncSession,
    model: type[T],
    slug: str,
) -> str:
    """Resolve a node's display title from its slug. Falls back to the slug itself."""
    result = await session.execute(
        select(model).where(model.slug == slug)
    )
    node = result.scalar_one_or_none()
    return node.title if node else slug
