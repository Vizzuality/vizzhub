"""Command queue management MCP tools — list, approve, reject queued commands."""

from __future__ import annotations

from uuid import UUID

from mcp.server.fastmcp import FastMCP

from mcp_server.data.base import get_mcp_user, get_write_session
from mcp_server.handlers import iso_docs as iso_handler
from mcp_server.handlers import playbook as playbook_handler
from mcp_server.services.command_service import CommandService
from mcp_server.tools._shared import to_json

_MODULE_PERMISSIONS = {
    "iso_docs": "iso_docs:edit",
    "playbook": "playbook:edit",
}

_MODULE_EXECUTORS = {
    "iso_docs": iso_handler.execute,
    "playbook": playbook_handler.execute,
}


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
        return to_json([
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
            return to_json({
                "error": f"Permission denied: requires {required_perm}",
                "user": user.email,
            })

        executor = _MODULE_EXECUTORS.get(cmd.module)
        if executor is None:
            return to_json({
                "error": f"No executor registered for module '{cmd.module}'",
            })

        cmd = await svc.approve(cmd_uuid, user_id, executor=executor)

        if cmd.status == "executed":
            return to_json({
                "status": "executed",
                "command_id": str(cmd.id),
                "result": cmd.result,
            })
        return to_json({
            "status": "failed",
            "command_id": str(cmd.id),
            "error": cmd.error,
        })


async def approve_all(module: str | None = None) -> str:
    """Approve and execute ALL your pending commands in a single call.

    Iterates your pending commands (optionally filtered by module), checks
    module permission, and executes each one. Each command is approved in
    its own transaction so a single failure does not block the rest.

    Args:
        module: Optional filter by module name ("iso_docs" or "playbook").
                Omit to approve pending commands from all modules.

    Returns JSON with total counts and a per-command result list
    (command_id, action, summary, status, error).
    """
    user = get_mcp_user()
    user_id = UUID(user.user_id)

    async with get_write_session() as session:
        svc = CommandService(session)
        pending = await svc.list_pending(user_id=user_id, module=module)
        command_ids = [cmd.id for cmd in pending]

    results: list[dict] = []
    counts = {"executed": 0, "failed": 0, "permission_denied": 0, "error": 0}

    for cmd_id in command_ids:
        try:
            async with get_write_session() as session:
                svc = CommandService(session)
                cmd = await svc.get_command(cmd_id)

                required_perm = _MODULE_PERMISSIONS.get(cmd.module)
                if required_perm and not user.has_permission(required_perm):
                    results.append({
                        "command_id": str(cmd.id),
                        "action": cmd.action,
                        "summary": cmd.summary,
                        "status": "permission_denied",
                        "error": f"requires {required_perm}",
                    })
                    counts["permission_denied"] += 1
                    continue

                executor = _MODULE_EXECUTORS.get(cmd.module)
                if executor is None:
                    results.append({
                        "command_id": str(cmd.id),
                        "action": cmd.action,
                        "summary": cmd.summary,
                        "status": "error",
                        "error": f"no executor for module '{cmd.module}'",
                    })
                    counts["error"] += 1
                    continue

                cmd = await svc.approve(cmd_id, user_id, executor=executor)
                results.append({
                    "command_id": str(cmd.id),
                    "action": cmd.action,
                    "summary": cmd.summary,
                    "status": cmd.status,
                    "error": cmd.error,
                })
                counts[cmd.status] = counts.get(cmd.status, 0) + 1
        except Exception as exc:
            results.append({
                "command_id": str(cmd_id),
                "status": "error",
                "error": str(exc),
            })
            counts["error"] += 1

    return to_json({
        "total": len(command_ids),
        "executed": counts["executed"],
        "failed": counts["failed"],
        "permission_denied": counts["permission_denied"],
        "errors": counts["error"],
        "results": results,
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
            return to_json({
                "error": f"Permission denied: requires {required_perm}",
                "user": user.email,
            })

        cmd = await svc.reject(cmd_uuid, user_id)
        return to_json({
            "status": "rejected",
            "command_id": str(cmd.id),
        })


def register_command_tools(server: FastMCP) -> None:
    """Register all command management tools on the given MCP server instance."""
    server.tool()(get_pending_commands)
    server.tool()(approve_command)
    server.tool()(approve_all)
    server.tool()(reject_command)
