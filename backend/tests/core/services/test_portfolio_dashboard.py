from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest

from app.core.models.client import ClientDB
from app.core.models.project import ProjectDB
from app.core.models.user import UserDB
from app.core.services.portfolio_dashboard import (
    build_client_leaderboard,
    build_project_leaderboard,
)
from app.modules.tracker.models.report import ReportDB
from app.modules.tracker.models.report_part import ReportPartDB
from app.modules.tracker.models.reporting_period import ReportingPeriodDB


async def _finished(db, **kw) -> ProjectDB:
    defaults = dict(
        is_billable=True,
        is_absence=False,
        status="finished",
        currency="euro",
        start_date=date(2023, 1, 1),
        end_date=date(2023, 6, 30),
        finished_at=date(2023, 8, 31),
    )
    defaults.update(kw)
    p = ProjectDB(
        name=kw.get("name", "P"),
        code=kw.get("code", "C"),
        **{k: v for k, v in defaults.items() if k not in ("name", "code")},
    )
    db.add(p)
    await db.flush()
    return p


async def _add_cost(db, project_id, amount: float, d: date = date(2023, 5, 1)) -> None:
    # ReportDB.user_id has a hard FK to users.id (ondelete=RESTRICT) so we must
    # create a real UserDB row — a bare uuid4() would violate the FK constraint.
    # ReportDB.estimated defaults to True; _valid_parts_filter excludes estimated=True
    # reports, so we must explicitly set estimated=False for costs to be counted.
    # ReportPartDB needs percentage > 0 for the same filter to include the row.
    user = UserDB(email=f"test-{uuid4()}@example.com")
    db.add(user)
    await db.flush()
    per = ReportingPeriodDB(date=d)
    db.add(per)
    await db.flush()
    r = ReportDB(reporting_period_id=per.id, user_id=user.id, estimated=False)
    db.add(r)
    await db.flush()
    db.add(
        ReportPartDB(
            report_id=r.id,
            project_id=project_id,
            cost=Decimal(str(amount)),
            percentage=Decimal("0.50"),
        )
    )
    await db.flush()


@pytest.mark.asyncio
async def test_scope_excludes_nonbillable_absence_live_and_budgetless(db_session):
    keep = await _finished(db_session, name="keep", code="K", budget=100000)
    await _add_cost(db_session, keep.id, 60000)
    await _finished(db_session, name="nb", code="NB", budget=100000, is_billable=False)
    # is_absence=True requires is_billable=False per DB check constraint
    await _finished(
        db_session, name="abs", code="AB", budget=100000, is_billable=False, is_absence=True
    )
    await _finished(db_session, name="live", code="LV", budget=100000, status="live")
    await _finished(db_session, name="nobudget", code="OPS", budget=None)
    await db_session.flush()

    board = await build_project_leaderboard(db_session)
    names = {r.name for r in board.rows}
    assert names == {"keep"}


@pytest.mark.asyncio
async def test_margin_and_profit_incl_negative_overrun(db_session):
    win = await _finished(db_session, name="win", code="W", budget=100000)
    await _add_cost(db_session, win.id, 60000)  # margin 40%, profit €40k
    over = await _finished(db_session, name="over", code="O", budget=100000)
    await _add_cost(db_session, over.id, 130000, d=date(2023, 6, 1))  # margin -30%, profit -€30k
    await db_session.flush()

    rows = {r.name: r for r in (await build_project_leaderboard(db_session)).rows}
    assert rows["win"].margin_pct == pytest.approx(40.0, abs=0.1)
    assert rows["win"].profit_eur == pytest.approx(40000, abs=1)
    assert rows["over"].margin_pct == pytest.approx(-30.0, abs=0.1)
    assert rows["over"].profit_eur == pytest.approx(-30000, abs=1)


@pytest.mark.asyncio
async def test_delay_months_from_finished_at(db_session):
    p = await _finished(
        db_session,
        name="late",
        code="L",
        budget=100000,
        end_date=date(2023, 6, 30),
        finished_at=date(2023, 9, 30),
    )
    await _add_cost(db_session, p.id, 50000)
    await db_session.flush()
    row = (await build_project_leaderboard(db_session)).rows[0]
    assert row.delay_months == 3


@pytest.mark.asyncio
async def test_unconvertible_currency_excluded_from_profit_only(db_session):
    # A currency with no exchange rate row => profit_eur None, margin still computed.
    # "ZZZ" is not a valid project currency per the DB check constraint;
    # use "GBP" instead (allowed by ck_projects_currency_valid) with no rate seeded.
    p = await _finished(db_session, name="xcur", code="X", budget=100000, currency="GBP")
    await _add_cost(db_session, p.id, 60000)
    await db_session.flush()
    row = (await build_project_leaderboard(db_session)).rows[0]
    assert row.margin_pct == pytest.approx(40.0, abs=0.1)
    assert row.profit_eur is None


@pytest.mark.asyncio
async def test_year_filter_and_available_years(db_session):
    a = await _finished(
        db_session, name="a2023", code="A", budget=100000, finished_at=date(2023, 4, 30)
    )
    await _add_cost(db_session, a.id, 50000)
    b = await _finished(
        db_session, name="b2024", code="B", budget=100000, finished_at=date(2024, 4, 30)
    )
    await _add_cost(db_session, b.id, 50000, d=date(2024, 4, 1))
    await db_session.flush()

    board = await build_project_leaderboard(db_session, year=2024)
    assert {r.name for r in board.rows} == {"b2024"}
    assert board.available_years == [2023, 2024]


@pytest.mark.asyncio
async def test_client_rollup_weighted_margin_and_unassigned_bucket(db_session):
    c = ClientDB(name="Acme", slug="acme", code="ACME")
    db_session.add(c)
    await db_session.flush()
    p1 = await _finished(db_session, name="p1", code="P1", budget=100000, client_id=c.id)
    await _add_cost(db_session, p1.id, 60000)  # profit 40k
    p2 = await _finished(db_session, name="p2", code="P2", budget=100000, client_id=c.id)
    await _add_cost(
        db_session, p2.id, 80000, d=date(2023, 6, 1)
    )  # profit 20k ; client margin = 60k/200k = 30%
    orphan = await _finished(db_session, name="orphan", code="ORP", budget=100000)
    await _add_cost(db_session, orphan.id, 50000, d=date(2023, 7, 1))
    await db_session.flush()

    board = await build_client_leaderboard(db_session)
    by_name = {r.client_name: r for r in board.rows}
    assert by_name["Acme"].project_count == 2
    assert by_name["Acme"].profit_eur == pytest.approx(60000, abs=1)
    assert by_name["Acme"].margin_pct == pytest.approx(30.0, abs=0.1)
    assert "— Unassigned" in by_name  # orphan bucket present
    assert by_name["— Unassigned"].project_count == 1
