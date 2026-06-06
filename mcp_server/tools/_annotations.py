"""Shared ToolAnnotations by category.

Tool annotations let MCP clients (Claude in particular) distinguish read tools
from write tools, so they can offer "Always allow" per category instead of
blocking it on every tool. Categories follow the registration convention:

- Read (get_/list_/search_/discover_, get_pending_commands): read-only, closed
  world (queries our own database).
- Read against a live third party (Jira): read-only, open world.
- Non-destructive write (create_/update_/patch_): mutates, not destructive, not
  idempotent.
- Destructive write (delete_): mutates and removes data.
- Command-queue gate (approve_command/approve_all/reject_command): mutates state
  (executes or discards queued commands), not destructive on its own.
"""

from __future__ import annotations

from mcp.types import ToolAnnotations

READ_ONLY = ToolAnnotations(readOnlyHint=True, openWorldHint=False)
READ_ONLY_OPEN_WORLD = ToolAnnotations(readOnlyHint=True, openWorldHint=True)
WRITE = ToolAnnotations(readOnlyHint=False, destructiveHint=False, idempotentHint=False)
DESTRUCTIVE = ToolAnnotations(readOnlyHint=False, destructiveHint=True)
COMMAND_GATE = ToolAnnotations(readOnlyHint=False, destructiveHint=False)
