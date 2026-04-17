"""Devstack user preferences endpoints."""

from uuid import UUID

import structlog
from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.core.api.deps import CurrentUser, DBSession
from app.modules.devstack.api.deps import get_entry_or_404
from app.modules.devstack.models.user_pref import DevstackUserPrefDB
from app.modules.devstack.schemas import UserPrefResponse, UserPrefUpdate

logger = structlog.get_logger()

router = APIRouter()


@router.get("/me/prefs")
async def list_my_prefs(
    db: DBSession,
    user: CurrentUser,
) -> list[UserPrefResponse]:
    result = await db.execute(
        select(DevstackUserPrefDB).where(DevstackUserPrefDB.user_id == user.user_id)
    )
    prefs = result.scalars().all()
    return [UserPrefResponse.model_validate(p) for p in prefs]


@router.put(
    "/me/prefs/{entry_id}",
    responses={404: {"description": "Devstack entry not found"}},
)
async def upsert_my_pref(
    entry_id: UUID,
    body: UserPrefUpdate,
    db: DBSession,
    user: CurrentUser,
) -> UserPrefResponse:
    # Verify the entry exists before upserting the pref
    await get_entry_or_404(db, entry_id)

    result = await db.execute(
        select(DevstackUserPrefDB).where(
            DevstackUserPrefDB.user_id == user.user_id,
            DevstackUserPrefDB.entry_id == entry_id,
        )
    )
    pref = result.scalar_one_or_none()

    if pref is None:
        pref = DevstackUserPrefDB(
            user_id=user.user_id,
            entry_id=entry_id,
            enabled=body.enabled,
        )
        db.add(pref)
    else:
        pref.enabled = body.enabled

    await db.commit()
    await db.refresh(pref)
    logger.info(
        "devstack_pref_updated",
        user_id=str(user.user_id),
        entry_id=str(entry_id),
        enabled=body.enabled,
    )
    return UserPrefResponse.model_validate(pref)
