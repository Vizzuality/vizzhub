"""ISO export API endpoints."""

from datetime import date, datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import AdminUser, DBSession, limiter
from app.core.services.export_helpers import XLSX_MEDIA_TYPE
from app.models.user import UserDB
from app.modules.iso.models.access_review import AccessReviewDB
from app.modules.iso.models.access_review_action import AccessReviewActionDB
from app.modules.iso.models.access_snapshot import AccessSnapshotDB
from app.modules.iso.services.export_service import IsoExportService

router = APIRouter()


def _parse_date_param(value: str, param_name: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid date format for '{param_name}': {value}. Use YYYY-MM-DD.",
        )


async def _build_export_data(
    db: AsyncSession, snapshots: list[AccessSnapshotDB],
) -> list[tuple[dict, dict | None, list[dict]]]:
    """Build the data tuples that IsoExportService expects."""
    user_cache: dict[UUID, str] = {}

    async def _resolve_email(user_id: UUID | None) -> str:
        if not user_id:
            return ""
        if user_id in user_cache:
            return user_cache[user_id]
        result = await db.execute(select(UserDB.email).where(UserDB.id == user_id))
        email = result.scalar_one_or_none() or ""
        user_cache[user_id] = email
        return email

    result = []
    for snapshot in snapshots:
        review_result = await db.execute(
            select(AccessReviewDB).where(
                AccessReviewDB.snapshot_id == snapshot.id
            )
        )
        review_db = review_result.scalar_one_or_none()

        review_dict = None
        actions_list: list[dict] = []

        if review_db:
            reviewer_email = await _resolve_email(review_db.reviewer_id)
            signed_by_email = await _resolve_email(review_db.signed_by)

            review_dict = {
                "id": str(review_db.id),
                "status": review_db.status,
                "scope": review_db.scope,
                "notes": review_db.notes,
                "reviewer_email": reviewer_email,
                "signed_by_email": signed_by_email,
                "signed_at": review_db.signed_at,
                "diff_summary": review_db.diff_summary,
            }

            actions_result = await db.execute(
                select(AccessReviewActionDB)
                .where(AccessReviewActionDB.review_id == review_db.id)
                .order_by(AccessReviewActionDB.created_at)
            )
            for action in actions_result.scalars().all():
                actions_list.append({
                    "subject_label": action.subject_label,
                    "subject_type": action.subject_type,
                    "subject_id": action.subject_id,
                    "change_type": action.change_type,
                    "previous_value": action.previous_value,
                    "current_value": action.current_value,
                    "action_taken": action.action_taken,
                    "justification": action.justification,
                    "exception_until": action.exception_until,
                })

        snapshot_dict = {
            "id": str(snapshot.id),
            "provider": snapshot.provider,
            "captured_at": snapshot.captured_at,
            "data_version": snapshot.data_version,
            "source_metadata": snapshot.source_metadata,
            "data": snapshot.data,
            "summary": snapshot.summary,
        }

        result.append((snapshot_dict, review_dict, actions_list))

    return result


@router.get(
    "",
    responses={400: {"description": "Invalid date format or range"}},
)
@limiter.limit("10/minute")
async def export_snapshot_range(
    request: Request,
    current_user: AdminUser,
    db: DBSession,
    from_date: Annotated[str, Query(alias="from", description="Start date (YYYY-MM-DD)")],
    to_date: Annotated[str, Query(alias="to", description="End date (YYYY-MM-DD)")],
) -> Response:
    start = _parse_date_param(from_date, "from")
    end = _parse_date_param(to_date, "to")

    if end < start:
        raise HTTPException(status_code=400, detail="'to' must not be before 'from'.")

    start_dt = datetime(start.year, start.month, start.day, tzinfo=timezone.utc)
    end_dt = datetime(end.year, end.month, end.day, 23, 59, 59, tzinfo=timezone.utc)

    result = await db.execute(
        select(AccessSnapshotDB)
        .where(AccessSnapshotDB.captured_at >= start_dt)
        .where(AccessSnapshotDB.captured_at <= end_dt)
        .order_by(AccessSnapshotDB.captured_at)
    )
    snapshots = list(result.scalars().all())

    export_data = await _build_export_data(db, snapshots)

    service = IsoExportService()
    output = service.export_snapshots(snapshots_with_reviews=export_data)

    filename = f"iso_access_review_{start}_{end}.xlsx"
    return Response(
        content=output.getvalue(),
        media_type=XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get(
    "/{snapshot_id}",
    responses={404: {"description": "Snapshot not found"}},
)
@limiter.limit("10/minute")
async def export_single_snapshot(
    request: Request,
    snapshot_id: UUID,
    current_user: AdminUser,
    db: DBSession,
) -> Response:
    result = await db.execute(
        select(AccessSnapshotDB).where(AccessSnapshotDB.id == snapshot_id)
    )
    snapshot = result.scalar_one_or_none()
    if not snapshot:
        raise HTTPException(status_code=404, detail="Snapshot not found")

    export_data = await _build_export_data(db, [snapshot])

    service = IsoExportService()
    output = service.export_snapshots(snapshots_with_reviews=export_data)

    captured_date = snapshot.captured_at.strftime("%Y-%m-%d")
    filename = f"iso_access_review_{captured_date}.xlsx"
    return Response(
        content=output.getvalue(),
        media_type=XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
