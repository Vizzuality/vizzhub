"""Capacity FA detail drill-down endpoint."""

from fastapi import APIRouter, HTTPException, Query

from app.core.api.deps import CurrentUser, DBSession
from app.core.services.capacity_insights import SHORT_TO_FA_NAME, get_capacity_fa_detail
from app.modules.capacity.api._validation import parse_month, validate_date_range

router = APIRouter()

_VALID_FA_CODES = set(SHORT_TO_FA_NAME.keys())


@router.get("")
async def capacity_fa_detail(
    db: DBSession,
    user: CurrentUser,
    fa: str = Query(..., description="FA short code (FE, BE, Design, PM, Sci, Coms)"),
    start_date: str = Query(..., description="Start month (YYYY-MM)"),
    end_date: str = Query(..., description="End month (YYYY-MM)"),
) -> list[dict]:
    if fa not in _VALID_FA_CODES:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid FA code: {fa}. Must be one of {sorted(_VALID_FA_CODES)}",
        )

    start = parse_month(start_date)
    end = parse_month(end_date)
    validate_date_range(start, end)
    return await get_capacity_fa_detail(db=db, fa_short=fa, start_date=start, end_date=end)
