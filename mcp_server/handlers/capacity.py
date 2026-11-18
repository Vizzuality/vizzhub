"""Capacity planner command handler — executes approved planner writes."""

from __future__ import annotations

from datetime import date
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.project import ProjectDB, ProjectStatus
from app.core.models.user import UserDB
from app.modules.capacity.public import CellUpdate, apply_cell_updates, clear_assignment_from
from mcp_server.data.capacity import current_monday

logger = structlog.get_logger()


async def _resolve_targets(session: AsyncSession, payload: dict) -> tuple[UserDB, ProjectDB]:
    try:
        user_id = UUID(payload["user_id"])
        project_id = UUID(payload["project_id"])
    except (KeyError, ValueError) as exc:
        raise ValueError("payload needs valid user_id and project_id") from exc
    user = await session.get(UserDB, user_id)
    if user is None or not user.active:
        raise ValueError(f"User {user_id} not found or inactive")
    project = await session.get(ProjectDB, project_id)
    if project is None:
        raise ValueError(f"Project {project_id} not found")
    if project.status == ProjectStatus.FINISHED:
        raise ValueError(f"Project '{project.name}' is finished and cannot be planned")
    return user, project


def _ensure_future(first: date) -> None:
    """Commands can wait in the queue; re-check the boundary at execution time."""
    if first < current_monday():
        raise ValueError(
            f"Week {first.isoformat()} is now in the past; the planner is future-only. "
            "Queue the command again with a current range."
        )


async def _set_allocation(payload: dict, user_id: UUID, session: AsyncSession) -> dict:
    user, project = await _resolve_targets(session, payload)
    weeks = sorted(date.fromisoformat(w) for w in payload.get("weeks") or [])
    if not weeks:
        raise ValueError("payload.weeks is empty")
    _ensure_future(weeks[0])

    percentage = int(payload["percentage"])
    extra = {"comment": payload["comment"]} if "comment" in payload else {}
    updates = [
        CellUpdate(
            project_id=project.id,
            user_id=user.id,
            week_start=week,
            percentage=percentage,
            **extra,
        )
        for week in weeks
    ]
    counts = await apply_cell_updates(session, updates, user_id)
    logger.info(
        "mcp_capacity_allocation_set",
        actor_id=str(user_id),
        target_user_id=str(user.id),
        project_id=str(project.id),
        percentage=percentage,
        weeks=len(weeks),
    )
    return {
        "user_id": str(user.id),
        "project_id": str(project.id),
        "percentage": percentage,
        "first_week": weeks[0].isoformat(),
        "last_week": weeks[-1].isoformat(),
        **counts,
    }


async def _clear_assignment(payload: dict, user_id: UUID, session: AsyncSession) -> dict:
    user, project = await _resolve_targets(session, payload)
    from_week = date.fromisoformat(payload["from_week"])
    _ensure_future(from_week)
    deleted = await clear_assignment_from(
        session, project_id=project.id, user_id=user.id, from_week=from_week
    )
    logger.info(
        "mcp_capacity_assignment_cleared",
        actor_id=str(user_id),
        target_user_id=str(user.id),
        project_id=str(project.id),
        from_week=from_week.isoformat(),
        deleted=deleted,
    )
    return {
        "user_id": str(user.id),
        "project_id": str(project.id),
        "from_week": from_week.isoformat(),
        "deleted": deleted,
    }


_ACTIONS = {
    "set_allocation": _set_allocation,
    "clear_assignment": _clear_assignment,
}


async def execute(
    action: str,
    _target: str | None,
    payload: dict,
    user_id: UUID,
    session: AsyncSession,
) -> dict:
    """Dispatch a capacity planner write action."""
    handler = _ACTIONS.get(action)
    if handler is None:
        raise ValueError(f"Unknown capacity action: '{action}'")
    return await handler(payload, user_id, session)
