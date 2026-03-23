"""Admin moods endpoint — aggregated mood data and feedback."""

import datetime
from collections import defaultdict
from uuid import UUID

from fastapi import APIRouter, Query
from sqlalchemy import func, select, tuple_

from app.core.api.deps import AdminUser, DBSession
from app.core.models.user import UserDB
from app.modules.tracker.models.anonymous_feedback import AnonymousFeedbackDB
from app.modules.tracker.models.report import ReportDB
from app.modules.tracker.models.reporting_period import ReportingPeriodDB
from app.modules.tracker.schemas.mood import (
    AnonymousFeedbackItem,
    MoodsResponse,
    MoodsTrendResponse,
    NamedFeedbackItem,
    TrendMonth,
)
from app.modules.tracker.api.helpers import get_or_404

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


@router.get("/trend")
async def get_moods_trend(
    db: DBSession,
    user: AdminUser,
) -> MoodsTrendResponse:
    today = datetime.date.today()
    target_months: list[tuple[int, int]] = []
    d = datetime.date(today.year, today.month, 1)
    for _ in range(12):
        if d.month == 1:
            d = datetime.date(d.year - 1, 12, 1)
        else:
            d = datetime.date(d.year, d.month - 1, 1)
        target_months.append((d.month, d.year))
    target_months.reverse()
    target_set = set(target_months)

    period_result = await db.execute(
        select(ReportingPeriodDB.id, ReportingPeriodDB.date)
    )
    period_to_month: dict[UUID, tuple[int, int]] = {}
    for pid, pdate in period_result.all():
        key = (pdate.month, pdate.year)
        if key in target_set:
            period_to_month[pid] = key

    all_period_ids = list(period_to_month.keys())

    reports_by_month: dict[tuple[int, int], list[tuple]] = defaultdict(list)
    if all_period_ids:
        reports_result = await db.execute(
            select(ReportDB, UserDB)
            .join(UserDB, ReportDB.user_id == UserDB.id)
            .where(ReportDB.reporting_period_id.in_(all_period_ids))
        )
        for report, db_user in reports_result.all():
            key = period_to_month[report.reporting_period_id]
            reports_by_month[key].append((report, db_user))

    anon_by_month: dict[tuple[int, int], list[AnonymousFeedbackDB]] = defaultdict(list)
    if target_months:
        anon_result = await db.execute(
            select(AnonymousFeedbackDB).where(
                tuple_(AnonymousFeedbackDB.month, AnonymousFeedbackDB.year).in_(
                    target_months
                )
            )
        )
        for fb in anon_result.scalars().all():
            anon_by_month[(fb.month, fb.year)].append(fb)

    months: list[TrendMonth] = []
    for m, y in target_months:
        label = datetime.date(y, m, 1).strftime("%b %Y")
        rows = reports_by_month.get((m, y), [])

        moods: list[int] = []
        named_feedback: list[NamedFeedbackItem] = []
        for report, db_user in rows:
            if report.mood is not None:
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

        anonymous_feedback = [
            AnonymousFeedbackItem(id=str(fb.id), text=fb.text)
            for fb in anon_by_month.get((m, y), [])
        ]

        avg = round(sum(moods) / len(moods), 1) if moods else None

        months.append(TrendMonth(
            month=m,
            year=y,
            label=label,
            average_mood=avg,
            total_responses=len(moods),
            total_reports=len(rows),
            anonymous_feedback=anonymous_feedback,
            named_feedback=named_feedback,
        ))

    return MoodsTrendResponse(months=months)


@router.delete("/anonymous/{feedback_id}", status_code=204)
async def delete_anonymous_feedback(
    feedback_id: UUID,
    db: DBSession,
    user: AdminUser,
) -> None:
    feedback = await get_or_404(AnonymousFeedbackDB, feedback_id, db, "Feedback")
    await db.delete(feedback)
    await db.commit()


@router.delete("/report/{report_id}/mood", status_code=204)
async def delete_report_mood(
    report_id: UUID,
    db: DBSession,
    user: AdminUser,
) -> None:
    report = await get_or_404(ReportDB, report_id, db, "Report")
    report.mood = None
    report.feedback_text = None
    await db.commit()
