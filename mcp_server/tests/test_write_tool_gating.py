"""HP-1 regression test: every MCP write tool must reject a non-editor user.

If a developer removes a `@mcp_requires` decorator from a write tool (or its
permission string drifts away from what the role actually grants), one of
these parametrized tests fails and CI catches the regression.

The `restricted_user` fixture only has `tracker:view`, so any tool that
requires `iso_docs:edit` or `playbook:edit` must raise ToolError.
"""

from __future__ import annotations

from typing import Any, Callable

import pytest
from mcp.server.fastmcp.exceptions import ToolError

from mcp_server.data.base import override_mcp_user
from mcp_server.tools.iso_write import (
    iso_create_page,
    iso_create_registry_row,
    iso_delete_node,
    iso_delete_registry_row,
    iso_patch_page_content,
    iso_update_node,
    iso_update_page_content,
    iso_update_page_metadata,
    iso_update_registry_row,
)
from mcp_server.tools.playbook_write import (
    playbook_create_article,
    playbook_delete_node,
    playbook_update_article_content,
    playbook_update_node,
)


# (tool_callable, required_permission, kwargs to call it with)
WRITE_TOOLS: list[tuple[Callable[..., Any], str, dict[str, Any]]] = [
    # ISO write tools — all require iso_docs:edit
    (iso_create_page, "iso_docs:edit", {"parent_slug": "policies", "title": "X"}),
    (iso_update_page_content, "iso_docs:edit", {"slug": "x", "content": "y"}),
    (
        iso_patch_page_content,
        "iso_docs:edit",
        {"slug": "x", "operations": []},
    ),
    (iso_update_page_metadata, "iso_docs:edit", {"slug": "x"}),
    (iso_update_node, "iso_docs:edit", {"slug": "x"}),
    (iso_delete_node, "iso_docs:edit", {"slug": "x"}),
    (
        iso_create_registry_row,
        "iso_docs:edit",
        {"slug": "x", "data": {}},
    ),
    (
        iso_update_registry_row,
        "iso_docs:edit",
        {"slug": "x", "row_id": "00000000-0000-0000-0000-000000000000", "data": {}},
    ),
    (
        iso_delete_registry_row,
        "iso_docs:edit",
        {"slug": "x", "row_id": "00000000-0000-0000-0000-000000000000"},
    ),
    # Playbook write tools — all require playbook:edit
    (playbook_create_article, "playbook:edit", {"parent_slug": "p", "title": "X"}),
    (playbook_update_article_content, "playbook:edit", {"slug": "x", "content": "y"}),
    (playbook_update_node, "playbook:edit", {"slug": "x"}),
    (playbook_delete_node, "playbook:edit", {"slug": "x"}),
]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("tool", "permission", "kwargs"),
    WRITE_TOOLS,
    ids=[t.__name__ for t, _, _ in WRITE_TOOLS],
)
async def test_write_tool_rejects_restricted_user(
    tool: Callable[..., Any],
    permission: str,
    kwargs: dict[str, Any],
    restricted_user,
) -> None:
    """Each write tool MUST raise ToolError when called by a non-editor.

    The restricted_user fixture has `tracker:view` only — never
    `iso_docs:edit` or `playbook:edit`. If this test passes for any tool,
    its permission gate is missing or wrong.
    """
    async with override_mcp_user(restricted_user):
        with pytest.raises(ToolError, match=f"requires {permission}"):
            await tool(**kwargs)
