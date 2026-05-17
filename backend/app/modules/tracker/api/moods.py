"""Admin moods endpoint — aggregated mood data and feedback."""

import datetime
from collections import defaultdict
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query
from sqlalchemy import func, select, tuple_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.api.deps import AdminUser, DBSession
from app.core.models.user import UserDB
from app.modules.tracker.api.helpers import get_or_404
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

router = APIRouter()


def _user_display_name(user: UserDB) -> str:
    if user.first_name and user.last_name:
        return f"{user.first_name} {user.last_name}"
    if user.name:
        return user.name
    return user.email.split("@")[0] if user.email else "Unknown"


def _collect_mood_feedback(
    rows: list[tuple],
) -> tuple[dict[int, int], list[int], list[NamedFeedbackItem]]:
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

    return mood_distribution, moods, named_feedback


@router.get("")
async def get_moods(
    db: DBSession,
    user: AdminUser,
    month: Annotated[int, Query(ge=1, le=12)],
    year: Annotated[int, Query(ge=2020, le=2100)],
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
        .where(
            ReportDB.reporting_period_id.in_(period_ids),
            ReportDB.estimated.is_(False),
        )
    )
    rows = reports_result.all()

    total_reports = len(rows)
    mood_distribution, moods, named_feedback = _collect_mood_feedback(rows)
    average_mood = sum(moods) / len(moods) if moods else None

    anon_result = await db.execute(
        select(AnonymousFeedbackDB).where(
            AnonymousFeedbackDB.month == month,
            AnonymousFeedbackDB.year == year,
        )
    )
    anonymous_feedback = [
        AnonymousFeedbackItem(id=str(r.id), text=r.text) for r in anon_result.scalars().all()
    ]

    return MoodsResponse(
        mood_distribution=mood_distribution,
        total_reports=total_reports,
        total_responses=len(moods),
        average_mood=round(average_mood, 1) if average_mood is not None else None,
        anonymous_feedback=anonymous_feedback,
        named_feedback=named_feedback,
    )


def _last_12_months() -> list[tuple[int, int]]:
    today = datetime.date.today()
    d = datetime.date(today.year, today.month, 1)
    months: list[tuple[int, int]] = []
    for _ in range(12):
        d = (
            datetime.date(d.year - 1, 12, 1)
            if d.month == 1
            else datetime.date(d.year, d.month - 1, 1)
        )
        months.append((d.month, d.year))
    months.reverse()
    return months


async def _reports_by_month(
    db: AsyncSession,
    target_months: list[tuple[int, int]],
) -> dict[tuple[int, int], list[tuple]]:
    target_set = set(target_months)
    period_result = await db.execute(select(ReportingPeriodDB.id, ReportingPeriodDB.date))
    period_to_month: dict[UUID, tuple[int, int]] = {
        pid: (pdate.month, pdate.year)
        for pid, pdate in period_result.all()
        if (pdate.month, pdate.year) in target_set
    }
    if not period_to_month:
        return defaultdict(list)

    reports_result = await db.execute(
        select(ReportDB, UserDB)
        .join(UserDB, ReportDB.user_id == UserDB.id)
        .where(
            ReportDB.reporting_period_id.in_(list(period_to_month.keys())),
            ReportDB.estimated.is_(False),
        )
    )
    result: dict[tuple[int, int], list[tuple]] = defaultdict(list)
    for report, db_user in reports_result.all():
        result[period_to_month[report.reporting_period_id]].append((report, db_user))
    return result


async def _anon_by_month(
    db: AsyncSession,
    target_months: list[tuple[int, int]],
) -> dict[tuple[int, int], list[AnonymousFeedbackDB]]:
    anon_result = await db.execute(
        select(AnonymousFeedbackDB).where(
            tuple_(AnonymousFeedbackDB.month, AnonymousFeedbackDB.year).in_(target_months)
        )
    )
    result: dict[tuple[int, int], list[AnonymousFeedbackDB]] = defaultdict(list)
    for fb in anon_result.scalars().all():
        result[(fb.month, fb.year)].append(fb)
    return result


def _build_trend_month(
    m: int,
    y: int,
    reports: list[tuple],
    anon_feedback: list[AnonymousFeedbackDB],
) -> TrendMonth:
    _, moods, named_feedback = _collect_mood_feedback(reports)
    return TrendMonth(
        month=m,
        year=y,
        label=datetime.date(y, m, 1).strftime("%b %Y"),
        average_mood=round(sum(moods) / len(moods), 1) if moods else None,
        total_responses=len(moods),
        total_reports=len(reports),
        anonymous_feedback=[
            AnonymousFeedbackItem(id=str(fb.id), text=fb.text) for fb in anon_feedback
        ],
        named_feedback=named_feedback,
    )


@router.get("/trend")
async def get_moods_trend(
    db: DBSession,
    user: AdminUser,
) -> MoodsTrendResponse:
    target_months = _last_12_months()
    reports = await _reports_by_month(db, target_months)
    anon = await _anon_by_month(db, target_months)

    months = [
        _build_trend_month(m, y, reports.get((m, y), []), anon.get((m, y), []))
        for m, y in target_months
    ]
    return MoodsTrendResponse(months=months)


@router.delete("/anonymous/{feedback_id}", status_code=204)
async def delete_anonymous_feedback(
    feedback_id: UUID,
    db: DBSession,
    user: AdminUser,
) -> None:
    feedback = await get_or_404(AnonymousFeedbackDB, feedback_id, db, "Feedback")
    await db.delete(feedback)
    await db.flush()


@router.delete("/report/{report_id}/mood", status_code=204)
async def delete_report_mood(
    report_id: UUID,
    db: DBSession,
    user: AdminUser,
) -> None:
    report = await get_or_404(ReportDB, report_id, db, "Report")
    report.mood = None
    report.feedback_text = None
    await db.flush()
