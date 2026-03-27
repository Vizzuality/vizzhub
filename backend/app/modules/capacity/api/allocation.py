"""Capacity allocation endpoints."""

from fastapi import APIRouter

from app.core.api.deps import CurrentUser, DBSession
from app.core.services.capacity_insights import get_allocation_users

router = APIRouter()


@router.get("/users")
async def allocation_users(
    db: DBSession,
    user: CurrentUser,
) -> dict:
    return await get_allocation_users(db=db)
