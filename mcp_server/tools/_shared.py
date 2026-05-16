"""Shared helpers for MCP tool modules."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

import structlog

from mcp_server.data.base import get_mcp_user, get_write_session
from mcp_server.services.command_service import CommandService
from mcp_server.services.summary import generate_summary

logger = structlog.get_logger()


def to_json(data: Any) -> str:
    """Serialize data to indented JSON with safe date/uuid handling."""
    return json.dumps(data, indent=2, default=str)


async def enqueue_command(module: str, action: str, target: str | None, payload: dict) -> str:
    """Generate summary, enqueue command, return JSON response."""
    user = get_mcp_user()
    user_id = UUID(user.user_id)
    async with get_write_session() as session:
        summary = await generate_summary(session, module, action, target, payload)
        svc = CommandService(session)
        cmd = await svc.enqueue(
            module=module,
            action=action,
            target=target,
            payload=payload,
            summary=summary,
            user_id=user_id,
        )
        logger.info(
            "mcp_command_enqueued",
            command_id=str(cmd.id),
            module=module,
            action=action,
            target=target,
            user_id=str(user_id),
            user_email=user.email,
        )
        return to_json({
            "status": "queued",
            "command_id": str(cmd.id),
            "summary": cmd.summary,
            "message": (
                "STOP. Command is queued but NOT executed. Present the "
                "summary above to the human user and wait for explicit "
                "confirmation (e.g. 'approve', 'ok', 'sí') before calling "
                f"approve_command('{cmd.id}'). Do NOT auto-approve."
            ),
        })
