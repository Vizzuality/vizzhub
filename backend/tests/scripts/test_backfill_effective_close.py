from datetime import date
from uuid import UUID

import pytest

from app.core.models.project import ProjectDB
from app.core.models.user import UserDB
from app.modules.tracker.models.report import ReportDB
from app.modules.tracker.models.report_part import ReportPartDB
from app.modules.tracker.models.reporting_period import ReportingPeriodDB
from app.scripts.backfill_effective_close import backfill_effective_close

_TEST_USER_ID = UUID("00000000-0000-0000-0000-000000000099")


async def _seed_user(db) -> UUID:
    user = UserDB(id=_TEST_USER_ID, email="backfill-test@example.com", name="Backfill Test")
    db.add(user)
    await db.flush()
    return user.id


async def _period(db, d: date) -> ReportingPeriodDB:
    p = ReportingPeriodDB(date=d)
    db.add(p)
    await db.flush()
    return p


async def _cost(db, project_id, period, amount: float, user_id: UUID) -> None:
    r = ReportDB(reporting_period_id=period.id, user_id=user_id)
    db.add(r)
    await db.flush()
    db.add(ReportPartDB(report_id=r.id, project_id=project_id, cost=amount))
    await db.flush()


@pytest.mark.asyncio
async def test_backfill_sets_effective_close_and_trims_trailing_residual(db_session):
    # Bulk of cost in 2022; a tiny stray report in 2025 must NOT drag the close date.
    user_id = await _seed_user(db_session)
    p = ProjectDB(
        name="Late residual",
        code="X.1",
        is_billable=True,
        is_absence=False,
        status="finished",
        budget=100000,
        currency="euro",
        start_date=date(2022, 1, 1),
        end_date=date(2022, 6, 30),
        finished_at=date(2022, 6, 30),  # migration default == end_date
    )
    db_session.add(p)
    await db_session.flush()
    jan = await _period(db_session, date(2022, 1, 1))
    feb = await _period(db_session, date(2022, 2, 1))
    stray = await _period(db_session, date(2025, 3, 1))
    await _cost(db_session, p.id, jan, 50000, user_id)
    await _cost(db_session, p.id, feb, 49000, user_id)  # 99% reached by Feb 2022
    await _cost(db_session, p.id, stray, 1000, user_id)  # 1% residual, 3 years later
    await db_session.flush()

    updated = await backfill_effective_close(db_session)
    await db_session.flush()
    await db_session.refresh(p)

    assert updated == 1
    assert p.finished_at == date(2022, 2, 1)  # 95% reached Feb 2022, stray trimmed


@pytest.mark.asyncio
async def test_backfill_protects_real_vizzhub_close_and_skips_no_reports(db_session):
    # finished_at differs from end_date => real VizzHub capture => must be left untouched.
    user_id = await _seed_user(db_session)
    real = ProjectDB(
        name="Real close",
        code="Y.1",
        is_billable=True,
        is_absence=False,
        status="finished",
        budget=50000,
        currency="euro",
        start_date=date(2023, 1, 1),
        end_date=date(2023, 3, 31),
        finished_at=date(2023, 5, 15),
    )
    # no reports at all => cannot reconstruct => skipped, finished_at unchanged.
    noreports = ProjectDB(
        name="No reports",
        code="Z.1",
        is_billable=True,
        is_absence=False,
        status="finished",
        budget=50000,
        currency="euro",
        start_date=date(2023, 1, 1),
        end_date=date(2023, 3, 31),
        finished_at=date(2023, 3, 31),
    )
    db_session.add_all([real, noreports])
    await db_session.flush()
    per = await _period(db_session, date(2023, 2, 1))
    await _cost(db_session, real.id, per, 10000, user_id)  # real has a report, but is protected
    await db_session.flush()

    updated = await backfill_effective_close(db_session)
    await db_session.flush()
    await db_session.refresh(real)
    await db_session.refresh(noreports)

    assert updated == 0
    assert real.finished_at == date(2023, 5, 15)  # protected
    assert noreports.finished_at == date(2023, 3, 31)  # skipped (no reports)
