"""Tool annotation tests — verify each tool advertises the right read/write hints.

MCP clients use ToolAnnotations to distinguish read tools from write tools (so
"Always allow" can be offered per category). These tests pin a representative
sample of each category against the registration convention, plus the two
explicit exceptions (Jira open-world read, command-queue gate).
"""

from __future__ import annotations

import pytest

from mcp_server.server import mcp

# name -> expected annotation fields (only the ones that matter for the category)
EXPECTED: dict[str, dict[str, bool]] = {
    # Read (closed world — our DB)
    "iso_get_documents": {"readOnlyHint": True, "openWorldHint": False},
    "tracker_get_projects": {"readOnlyHint": True, "openWorldHint": False},
    "get_pending_commands": {"readOnlyHint": True, "openWorldHint": False},
    # Read exception — hits live Jira → open world
    "tracker_get_user_jira_issues": {"readOnlyHint": True, "openWorldHint": True},
    # Non-destructive writes
    "iso_create_page": {
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    },
    "iso_update_page_content": {
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    },
    "playbook_create_article": {
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
    },
    # Destructive writes
    "iso_delete_node": {"readOnlyHint": False, "destructiveHint": True},
    "playbook_delete_node": {"readOnlyHint": False, "destructiveHint": True},
    # Command-queue gate — mutates, not a read, not destructive on its own
    "approve_command": {"readOnlyHint": False, "destructiveHint": False},
    "approve_all": {"readOnlyHint": False, "destructiveHint": False},
    "reject_command": {"readOnlyHint": False, "destructiveHint": False},
}


@pytest.mark.asyncio
async def test_every_tool_has_annotations() -> None:
    """No tool ships without annotations — clients can't gate an un-annotated tool."""
    tools = await mcp.list_tools()
    missing = [t.name for t in tools if t.annotations is None]
    assert not missing, f"tools missing annotations: {missing}"


@pytest.mark.asyncio
@pytest.mark.parametrize(("name", "expected"), EXPECTED.items())
async def test_tool_annotation_matches_category(name: str, expected: dict[str, bool]) -> None:
    """A sample of each category advertises the hints its convention requires."""
    tools = {t.name: t for t in await mcp.list_tools()}
    assert name in tools, f"{name} is not registered"

    annotations = tools[name].annotations
    assert annotations is not None, f"{name} has no annotations"

    for field, value in expected.items():
        actual = getattr(annotations, field)
        assert actual == value, (
            f"{name}.{field} = {actual!r}, expected {value!r}"
        )
