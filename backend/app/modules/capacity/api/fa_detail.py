"""Capacity FA detail drill-down endpoint."""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from app.core.api.deps import CurrentUser, DBSession
from app.core.services.capacity_insights import SHORT_TO_FA_NAME, get_capacity_fa_detail
from app.modules.capacity.api._validation import MonthRangeDep

router = APIRouter()

_VALID_FA_CODES = set(SHORT_TO_FA_NAME.keys())


@router.get("", responses={422: {"description": "Invalid FA code or date format"}})
async def capacity_fa_detail(
    db: DBSession,
    user: CurrentUser,
    fa: Annotated[str, Query(description="FA short code (FE, BE, Design, PM, Sci, Coms)")],
    months: MonthRangeDep,
) -> list[dict]:
    if fa not in _VALID_FA_CODES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid FA code: {fa}. Must be one of {sorted(_VALID_FA_CODES)}",
        )

    return await get_capacity_fa_detail(
        db=db, fa_short=fa, start_date=months.start, end_date=months.end
    )
