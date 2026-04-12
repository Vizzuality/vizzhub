"""Command queue management MCP tools — list, approve, reject queued commands."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from mcp.server.fastmcp import FastMCP

from mcp_server.auth.permissions import mcp_requires
from mcp_server.data.base import get_mcp_user, get_write_session
from mcp_server.handlers import iso_docs as iso_handler
from mcp_server.handlers import playbook as playbook_handler
from mcp_server.services.command_service import CommandService

_MODULE_PERMISSIONS = {
    "iso_docs": "iso_docs:edit",
    "playbook": "playbook:edit",
}

_MODULE_EXECUTORS = {
    "iso_docs": iso_handler.execute,
    "playbook": playbook_handler.execute,
}


def _to_json(data: Any) -> str:
    """Serialize data to indented JSON with safe date/uuid handling."""
    return json.dumps(data, indent=2, default=str)


async def get_pending_commands(module: str | None = None) -> str:
    """List your pending commands awaiting approval.

    Returns all commands you have queued that are still in "pending" status.
    Use approve_command() or reject_command() on any returned command_id.

    Args:
        module: Optional filter by module name ("iso_docs" or "playbook").
                Omit to see all pending commands.

    Returns JSON array of pending commands with command_id, module,
    action, summary, and requested_at timestamp.
    """
    user = get_mcp_user()
    user_id = UUID(user.user_id)
    async with get_write_session() as session:
        svc = CommandService(session)
        commands = await svc.list_pending(user_id=user_id, module=module)
        return _to_json([
            {
                "command_id": str(cmd.id),
                "module": cmd.module,
                "action": cmd.action,
                "summary": cmd.summary,
                "requested_at": cmd.requested_at,
            }
            for cmd in commands
        ])


async def approve_command(command_id: str) -> str:
    """Approve and execute a pending command.

    Verifies you have permission for the command's module, then executes
    the queued action immediately. The command transitions from "pending"
    to "executed" (success) or "failed" (if execution raises an error).

    Args:
        command_id: UUID of the command to approve (from get_pending_commands
                    or from a write tool's response).

    Returns JSON with status ("executed" or "failed"), command_id,
    and the execution result or error message.
    """
    user = get_mcp_user()
    user_id = UUID(user.user_id)
    cmd_uuid = UUID(command_id)

    async with get_write_session() as session:
        svc = CommandService(session)
        cmd = await svc.get_command(cmd_uuid)

        required_perm = _MODULE_PERMISSIONS.get(cmd.module)
        if required_perm and not user.has_permission(required_perm):
            return _to_json({
                "error": f"Permission denied: requires {required_perm}",
                "user": user.email,
            })

        executor = _MODULE_EXECUTORS.get(cmd.module)
        if executor is None:
            return _to_json({
                "error": f"No executor registered for module '{cmd.module}'",
            })

        cmd = await svc.approve(cmd_uuid, user_id, executor=executor)

        if cmd.status == "executed":
            return _to_json({
                "status": "executed",
                "command_id": str(cmd.id),
                "result": cmd.result,
            })
        else:
            return _to_json({
                "status": "failed",
                "command_id": str(cmd.id),
                "error": cmd.error,
            })


async def reject_command(command_id: str) -> str:
    """Reject a pending command, discarding it without executing.

    The command transitions to "rejected" and cannot be approved later.

    Args:
        command_id: UUID of the command to reject (from get_pending_commands
                    or from a write tool's response).

    Returns JSON with status "rejected" and the command_id.
    """
    user = get_mcp_user()
    user_id = UUID(user.user_id)
    cmd_uuid = UUID(command_id)

    async with get_write_session() as session:
        svc = CommandService(session)
        cmd = await svc.get_command(cmd_uuid)

        required_perm = _MODULE_PERMISSIONS.get(cmd.module)
        if required_perm and not user.has_permission(required_perm):
            return _to_json({
                "error": f"Permission denied: requires {required_perm}",
                "user": user.email,
            })

        cmd = await svc.reject(cmd_uuid, user_id)
        return _to_json({
            "status": "rejected",
            "command_id": str(cmd.id),
        })


def register_command_tools(server: FastMCP) -> None:
    """Register all command management tools on the given MCP server instance."""
    server.tool()(get_pending_commands)
    server.tool()(approve_command)
    server.tool()(reject_command)
