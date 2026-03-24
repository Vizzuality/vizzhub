"""Tests for playbook tree service."""

import pytest

from app.modules.playbook.services.tree_service import (
    generate_slug,
    get_next_position,
    validate_depth,
    validate_not_circular,
    MAX_DEPTH,
)
from app.modules.playbook.models.node import PlaybookNodeDB


def test_generate_slug_basic():
    assert generate_slug("Getting Started") == "getting-started"


def test_generate_slug_special_chars():
    assert generate_slug("What's New? (2026)") == "whats-new-2026"


def test_generate_slug_unicode():
    result = generate_slug("Guía de Inicio")
    assert result == "guia-de-inicio"


@pytest.mark.asyncio
async def test_get_next_position_empty(db_session):
    pos = await get_next_position(db_session, parent_id=None)
    assert pos == 0


@pytest.mark.asyncio
async def test_get_next_position_with_siblings(db_session):
    node = PlaybookNodeDB(
        title="First",
        slug="first",
        type="page",
        parent_id=None,
        position=0,
        created_by_id=None,
        updated_by_id=None,
    )
    db_session.add(node)
    await db_session.flush()

    pos = await get_next_position(db_session, parent_id=None)
    assert pos == 1


@pytest.mark.asyncio
async def test_validate_depth_root_ok(db_session):
    assert await validate_depth(db_session, parent_id=None) is True


@pytest.mark.asyncio
async def test_validate_depth_too_deep(db_session):
    parent_id = None
    for i in range(MAX_DEPTH):
        node = PlaybookNodeDB(
            title=f"Level {i}",
            slug=f"level-{i}",
            type="group",
            parent_id=parent_id,
            position=0,
            created_by_id=None,
            updated_by_id=None,
        )
        db_session.add(node)
        await db_session.flush()
        parent_id = node.id

    assert await validate_depth(db_session, parent_id=parent_id) is False


@pytest.mark.asyncio
async def test_validate_not_circular(db_session):
    parent = PlaybookNodeDB(
        title="Parent", slug="parent", type="group",
        parent_id=None, position=0,
        created_by_id=None, updated_by_id=None,
    )
    db_session.add(parent)
    await db_session.flush()

    child = PlaybookNodeDB(
        title="Child", slug="child", type="group",
        parent_id=parent.id, position=0,
        created_by_id=None, updated_by_id=None,
    )
    db_session.add(child)
    await db_session.flush()

    assert await validate_not_circular(db_session, node_id=parent.id, new_parent_id=child.id) is False
    assert await validate_not_circular(db_session, node_id=child.id, new_parent_id=None) is True
