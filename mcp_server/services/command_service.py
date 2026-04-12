"""Command queue service — enqueue, approve, reject, list."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from mcp_server.models.command import CommandDB

Executor = Callable[
    [str, str | None, dict, UUID, AsyncSession],
    Awaitable[dict],
]


class CommandService:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def enqueue(
        self,
        *,
        module: str,
        action: str,
        target: str | None,
        payload: dict,
        summary: str,
        user_id: UUID,
    ) -> CommandDB:
        cmd = CommandDB(
            module=module,
            action=action,
            target=target,
            payload=payload,
            summary=summary,
            requested_by=user_id,
        )
        self._session.add(cmd)
        await self._session.flush()
        await self._session.refresh(cmd)
        return cmd

    async def approve(
        self,
        command_id: UUID,
        reviewer_id: UUID,
        *,
        executor: Executor,
    ) -> CommandDB:
        cmd = await self.get_command(command_id)
        if cmd.status != "pending":
            raise ValueError(
                f"Command {command_id} is not pending (status={cmd.status})"
            )

        now = datetime.now(timezone.utc)
        cmd.status = "approved"
        cmd.reviewed_by = reviewer_id
        cmd.reviewed_at = now

        try:
            result = await executor(
                cmd.action, cmd.target, cmd.payload, cmd.requested_by, self._session,
            )
            cmd.status = "executed"
            cmd.result = result
            cmd.executed_at = datetime.now(timezone.utc)
        except Exception as exc:
            cmd.status = "failed"
            cmd.error = str(exc)

        await self._session.flush()
        await self._session.refresh(cmd)
        return cmd

    async def reject(self, command_id: UUID, reviewer_id: UUID) -> CommandDB:
        cmd = await self.get_command(command_id)
        if cmd.status != "pending":
            raise ValueError(
                f"Command {command_id} is not pending (status={cmd.status})"
            )

        cmd.status = "rejected"
        cmd.reviewed_by = reviewer_id
        cmd.reviewed_at = datetime.now(timezone.utc)
        await self._session.flush()
        await self._session.refresh(cmd)
        return cmd

    async def list_pending(
        self,
        *,
        user_id: UUID | None = None,
        module: str | None = None,
    ) -> list[CommandDB]:
        stmt = (
            select(CommandDB)
            .where(CommandDB.status == "pending")
            .order_by(CommandDB.requested_at)
        )
        if user_id is not None:
            stmt = stmt.where(CommandDB.requested_by == user_id)
        if module is not None:
            stmt = stmt.where(CommandDB.module == module)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_command(self, command_id: UUID) -> CommandDB:
        result = await self._session.execute(
            select(CommandDB).where(CommandDB.id == command_id)
        )
        cmd = result.scalar_one_or_none()
        if cmd is None:
            raise ValueError(f"Command {command_id} not found")
        return cmd
