"""Lightweight user list endpoint accessible to any authenticated user."""

from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select

from app.core.api.deps import CurrentUser, DBSession
from app.core.models.user import UserDB

router = APIRouter(prefix="/users", tags=["users"])


class UserSummary(BaseModel):
    """Minimal user info for dropdowns and selectors."""

    id: UUID
    email: str
    first_name: str | None = None
    last_name: str | None = None
    active: bool = True

    model_config = {"from_attributes": True}


@router.get("")
async def list_users(
    current_user: CurrentUser,
    db: DBSession,
) -> list[UserSummary]:
    """List active users. Available to any authenticated user."""
    result = await db.execute(select(UserDB).where(UserDB.active.is_(True)).order_by(UserDB.name))
    return [UserSummary.model_validate(u) for u in result.scalars().all()]
