"""Global Metrics API endpoints."""

from fastapi import APIRouter, HTTPException, Query, Request

from app.api.deps import CurrentUser, DBSession, ScoringConfigDep, limiter
from app.models.global_metrics import (
    CalculateBatchRequest,
    CalculateBatchResponse,
    GlobalMetricsHistoryResponse,
    GlobalMetricsRecord,
)
from app.services.global_metrics_service import GlobalMetricsService

router = APIRouter(prefix="/global", tags=["global"])


def get_service(config: ScoringConfigDep) -> GlobalMetricsService:
    """Create GlobalMetricsService with injected config."""
    return GlobalMetricsService(config)


@router.get("/history", response_model=GlobalMetricsHistoryResponse)
@limiter.limit("100/minute")
async def get_global_metrics_history(
    request: Request,
    db: DBSession,
    config: ScoringConfigDep,
    current_user: CurrentUser,
    limit: int = Query(12, ge=1, le=48, description="Number of months to return"),
) -> GlobalMetricsHistoryResponse:
    """Get historical global metrics for trend display.

    Returns the most recent months first, up to the specified limit.
    """
    service = get_service(config)
    records = await service.get_history(db, limit)
    return GlobalMetricsHistoryResponse(
        records=[GlobalMetricsRecord.from_db(r) for r in records]
    )


@router.get("/available-months")
@limiter.limit("100/minute")
async def get_available_months(
    request: Request,
    db: DBSession,
    config: ScoringConfigDep,
    current_user: CurrentUser,
) -> list[dict[str, int]]:
    """Get list of months that have stored global metrics.

    Returns list of {year, month} objects ordered by most recent first.
    """
    service = get_service(config)
    months = await service.get_available_months(db)
    return [{"year": year, "month": month} for year, month in months]


@router.get("/{year}/{month}", response_model=GlobalMetricsRecord | None)
@limiter.limit("100/minute")
async def get_global_metrics(
    request: Request,
    year: int,
    month: int,
    db: DBSession,
    config: ScoringConfigDep,
    current_user: CurrentUser,
) -> GlobalMetricsRecord | None:
    """Get stored global metrics for a specific month.

    Returns None if no metrics have been calculated for this month.
    """
    if month < 1 or month > 12:
        raise HTTPException(400, "month must be between 1 and 12")

    service = get_service(config)
    record = await service.get_record(db, year, month)

    if not record:
        return None

    return GlobalMetricsRecord.from_db(record)


@router.post("/calculate", response_model=CalculateBatchResponse)
@limiter.limit("10/minute")
async def calculate_global_metrics(
    request: Request,
    batch_request: CalculateBatchRequest,
    db: DBSession,
    config: ScoringConfigDep,
    current_user: CurrentUser,
) -> CalculateBatchResponse:
    """Calculate and store global metrics for a date range (batch).

    This endpoint:
    1. Fetches all project metrics for each month in the range
    2. Computes scores for each project
    3. Averages indicators and scores across projects
    4. Stores/updates the global metrics record for each month

    Use this to populate initial data or update after config changes.
    """
    if (batch_request.from_year, batch_request.from_month) > (
        batch_request.to_year,
        batch_request.to_month,
    ):
        raise HTTPException(400, "from_date must be before or equal to to_date")

    if batch_request.from_year < 2023:
        raise HTTPException(400, "from_year must be 2023 or later")

    service = get_service(config)
    records = await service.calculate_batch(
        db,
        batch_request.from_year,
        batch_request.from_month,
        batch_request.to_year,
        batch_request.to_month,
    )

    return CalculateBatchResponse(
        months_processed=len(records),
        records=[GlobalMetricsRecord.from_db(r) for r in records],
    )


@router.post("/recalculate", response_model=CalculateBatchResponse)
@limiter.limit("10/minute")
async def recalculate_global_metrics(
    request: Request,
    batch_request: CalculateBatchRequest,
    db: DBSession,
    config: ScoringConfigDep,
    current_user: CurrentUser,
) -> CalculateBatchResponse:
    """Recalculate global metrics with current weights for a date range.

    Same as /calculate - the upsert behavior handles overwriting.
    Use this after changing weights/targets in configuration.
    """
    return await calculate_global_metrics(
        request, batch_request, db, config, current_user
    )
