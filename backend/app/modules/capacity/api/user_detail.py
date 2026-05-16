"""Capacity user detail drill-down endpoint."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from app.core.api.deps import CurrentUser, DBSession
from app.core.services.capacity_insights import (
    get_capacity_user_detail,
    get_reportable_users,
)
from app.modules.capacity.api._validation import MonthRangeDep

router = APIRouter()


@router.get("/users")
async def reportable_users(
    db: DBSession,
    user: CurrentUser,
) -> list[dict]:
    return await get_reportable_users(db)


@router.get("", responses={422: {"description": "Invalid user_id or date format"}})
async def capacity_user_detail(
    db: DBSession,
    user: CurrentUser,
    user_id: Annotated[str, Query(description="User UUID")],
    months: MonthRangeDep,
) -> list[dict]:
    try:
        UUID(user_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=f"Invalid user_id: {user_id}") from exc

    return await get_capacity_user_detail(
        db=db, user_id=user_id, start_date=months.start, end_date=months.end
    )
