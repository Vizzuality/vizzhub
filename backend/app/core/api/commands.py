"""Command queue REST API — list, approve, reject pending commands."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

import structlog
from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from app.core.api.deps import AdminUser, DBSession

logger = structlog.get_logger()

router = APIRouter(tags=["commands"])


def _get_command_model():
    from mcp_server.models.command import CommandDB
    return CommandDB


def _serialize_command(cmd) -> dict:
    """Convert a CommandDB row to a JSON-safe dict."""
    return {
        "id": str(cmd.id),
        "module": cmd.module,
        "action": cmd.action,
        "target": cmd.target,
        "payload": cmd.payload,
        "summary": cmd.summary,
        "status": cmd.status,
        "requested_by": str(cmd.requested_by),
        "requested_at": cmd.requested_at.isoformat() if cmd.requested_at else None,
        "reviewed_by": str(cmd.reviewed_by) if cmd.reviewed_by else None,
        "reviewed_at": cmd.reviewed_at.isoformat() if cmd.reviewed_at else None,
        "executed_at": cmd.executed_at.isoformat() if cmd.executed_at else None,
        "result": cmd.result,
        "error": cmd.error,
    }


@router.get("/commands")
async def list_commands(
    db: DBSession,
    _user: AdminUser,
    status: Annotated[str | None, Query()] = None,
    module: Annotated[str | None, Query()] = None,
) -> list[dict]:
    """List commands, optionally filtered by status and/or module."""
    command_model = _get_command_model()
    stmt = select(command_model).order_by(command_model.requested_at.desc())
    if status is not None:
        stmt = stmt.where(command_model.status == status)
    if module is not None:
        stmt = stmt.where(command_model.module == module)
    result = await db.execute(stmt)
    return [_serialize_command(cmd) for cmd in result.scalars().all()]


@router.post(
    "/commands/{command_id}/approve",
    responses={
        404: {"description": "Command not found"},
        400: {"description": "Command is not pending"},
    },
)
async def approve_command(
    command_id: UUID,
    db: DBSession,
    user: AdminUser,
) -> dict:
    """Approve a pending command and execute its handler."""
    from mcp_server.handlers import iso_docs as iso_handler
    from mcp_server.handlers import playbook as playbook_handler
    from mcp_server.services.command_service import CommandService

    handlers: dict = {
        "iso_docs": iso_handler.execute,
        "playbook": playbook_handler.execute,
    }

    svc = CommandService(db)

    try:
        cmd = await svc.get_command(command_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Command not found")

    executor = handlers.get(cmd.module)
    if executor is None:
        raise HTTPException(
            status_code=400,
            detail=f"No handler registered for module '{cmd.module}'",
        )

    try:
        cmd = await svc.approve(
            command_id, UUID(user.user_id), executor=executor,
        )
    except ValueError as exc:
        msg = str(exc)
        if "not found" in msg:
            raise HTTPException(status_code=404, detail=msg)
        raise HTTPException(status_code=400, detail=msg)

    logger.info(
        "command_approved_via_api",
        command_id=str(command_id),
        reviewer_id=user.user_id,
        status=cmd.status,
    )
    return {
        "status": cmd.status,
        "result": cmd.result,
        "error": cmd.error,
    }


@router.post(
    "/commands/{command_id}/reject",
    responses={
        404: {"description": "Command not found"},
        400: {"description": "Command is not pending"},
    },
)
async def reject_command(
    command_id: UUID,
    db: DBSession,
    user: AdminUser,
) -> dict:
    """Reject a pending command."""
    from mcp_server.services.command_service import CommandService

    svc = CommandService(db)

    try:
        await svc.reject(command_id, UUID(user.user_id))
    except ValueError as exc:
        msg = str(exc)
        if "not found" in msg:
            raise HTTPException(status_code=404, detail=msg)
        raise HTTPException(status_code=400, detail=msg)

    logger.info(
        "command_rejected_via_api",
        command_id=str(command_id),
        reviewer_id=user.user_id,
    )
    return {"status": "rejected"}
