"""Admin moods endpoint — aggregated mood data and feedback."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func, select

from app.core.api.deps import AdminUser, DBSession
from app.core.models.user import UserDB
from app.modules.tracker.models.anonymous_feedback import AnonymousFeedbackDB
from app.modules.tracker.models.report import ReportDB
from app.modules.tracker.models.reporting_period import ReportingPeriodDB
from app.modules.tracker.schemas.mood import (
    AnonymousFeedbackItem,
    MoodsResponse,
    NamedFeedbackItem,
)

router = APIRouter()


def _user_display_name(user: UserDB) -> str:
    if user.first_name and user.last_name:
        return f"{user.first_name} {user.last_name}"
    if user.name:
        return user.name
    return user.email.split("@")[0] if user.email else "Unknown"


@router.get("")
async def get_moods(
    db: DBSession,
    user: AdminUser,
    month: int = Query(ge=1, le=12),
    year: int = Query(ge=2020, le=2100),
) -> MoodsResponse:
    period_result = await db.execute(
        select(ReportingPeriodDB.id).where(
            func.extract("month", ReportingPeriodDB.date) == month,
            func.extract("year", ReportingPeriodDB.date) == year,
        )
    )
    period_ids = [r[0] for r in period_result.all()]

    if not period_ids:
        return MoodsResponse(
            mood_distribution={},
            total_reports=0,
            total_responses=0,
            average_mood=None,
            anonymous_feedback=[],
            named_feedback=[],
        )

    reports_result = await db.execute(
        select(ReportDB, UserDB)
        .join(UserDB, ReportDB.user_id == UserDB.id)
        .where(ReportDB.reporting_period_id.in_(period_ids))
    )
    rows = reports_result.all()

    total_reports = len(rows)
    mood_distribution: dict[int, int] = {}
    moods: list[int] = []
    named_feedback: list[NamedFeedbackItem] = []

    for report, db_user in rows:
        if report.mood is not None:
            mood_distribution[report.mood] = mood_distribution.get(report.mood, 0) + 1
            moods.append(report.mood)

        if report.mood is not None or report.feedback_text is not None:
            named_feedback.append(
                NamedFeedbackItem(
                    report_id=str(report.id),
                    user_name=_user_display_name(db_user),
                    mood=report.mood,
                    text=report.feedback_text,
                )
            )

    average_mood = sum(moods) / len(moods) if moods else None

    anon_result = await db.execute(
        select(AnonymousFeedbackDB).where(
            AnonymousFeedbackDB.month == month,
            AnonymousFeedbackDB.year == year,
        )
    )
    anonymous_feedback = [
        AnonymousFeedbackItem(id=str(r.id), text=r.text)
        for r in anon_result.scalars().all()
    ]

    return MoodsResponse(
        mood_distribution=mood_distribution,
        total_reports=total_reports,
        total_responses=len(moods),
        average_mood=round(average_mood, 1) if average_mood is not None else None,
        anonymous_feedback=anonymous_feedback,
        named_feedback=named_feedback,
    )


@router.delete("/anonymous/{feedback_id}", status_code=204)
async def delete_anonymous_feedback(
    feedback_id: UUID,
    db: DBSession,
    user: AdminUser,
) -> None:
    result = await db.execute(
        select(AnonymousFeedbackDB).where(AnonymousFeedbackDB.id == feedback_id)
    )
    feedback = result.scalar_one_or_none()
    if not feedback:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Feedback not found")
    await db.delete(feedback)
    await db.commit()


@router.delete("/report/{report_id}/mood", status_code=204)
async def delete_report_mood(
    report_id: UUID,
    db: DBSession,
    user: AdminUser,
) -> None:
    result = await db.execute(
        select(ReportDB).where(ReportDB.id == report_id)
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Report not found")
    report.mood = None
    report.feedback_text = None
    await db.commit()
