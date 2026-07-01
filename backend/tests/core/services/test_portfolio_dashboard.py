"""Unit tests for the portfolio analytics dashboard service."""

from datetime import date
from decimal import Decimal

import pytest

from app.core.models.client import ClientDB
from app.core.models.project import ProjectDB
from app.core.models.user import UserDB
from app.core.services.portfolio_dashboard import build_portfolio_summary
from app.modules.tracker.models.report import ReportDB
from app.modules.tracker.models.report_part import ReportPartDB
from app.modules.tracker.models.reporting_period import ReportingPeriodDB


async def _project(db, **kw):
    defaults = dict(is_billable=True, is_absence=False, status="live", currency="EUR")
    defaults.update(kw)
    p = ProjectDB(**defaults)
    db.add(p)
    await db.flush()
    return p


async def _cost_fixtures(
    db, project, *, cost: float, currency: str = "EUR", period_date: date = date(2024, 1, 1)
) -> None:
    """Insert the minimal chain for real non-zero cost: period → user → report → part.

    The project's currency is set on creation; this just drives a non-zero
    total_cost through ReportPartDB so get_batch_cost_summaries returns > 0.
    ``estimated=False`` is required; estimated reports are excluded from sums.
    Pass a unique ``period_date`` when calling multiple times in the same test
    to avoid the unique constraint on reporting_periods.date.
    """
    period = ReportingPeriodDB(
        date=period_date,
        base_rate=Decimal("175"),
        status="active",
    )
    db.add(period)
    await db.flush()

    user = UserDB(email=f"test-{project.id}@example.com")
    db.add(user)
    await db.flush()

    report = ReportDB(
        user_id=user.id,
        reporting_period_id=period.id,
        estimated=False,
    )
    db.add(report)
    await db.flush()

    part = ReportPartDB(
        report_id=report.id,
        project_id=project.id,
        percentage=Decimal("0.50"),
        cost=Decimal(str(cost)),
        days=Decimal("10"),
    )
    db.add(part)
    await db.flush()


@pytest.mark.asyncio
async def test_volume_by_year_expands_start_to_end(db_session):
    await _project(
        db_session, name="Multi-year", start_date=date(2020, 3, 1), end_date=date(2022, 6, 1)
    )
    await _project(db_session, name="Single-year", start_date=date(2021, 1, 1), end_date=None)
    summary = await build_portfolio_summary(db_session, year=None)
    counts = {v.year: v.count for v in summary.volume_by_year}
    assert counts == {2020: 1, 2021: 2, 2022: 1}
    assert summary.available_years == [2020, 2021, 2022]


@pytest.mark.asyncio
async def test_absence_and_non_billable_excluded(db_session):
    await _project(
        db_session, name="Billable", start_date=date(2021, 1, 1), is_billable=True, is_absence=False
    )
    await _project(
        db_session, name="Absence", start_date=date(2021, 1, 1), is_billable=False, is_absence=True
    )
    summary = await build_portfolio_summary(db_session, year=None)
    assert summary.kpis.project_count == 1


@pytest.mark.asyncio
async def test_margin_split_excludes_none_burn(db_session):
    # No budget -> burn_percentage is None -> counts as no_data, excluded from avg.
    await _project(db_session, name="No budget", start_date=date(2021, 1, 1), budget=None)
    summary = await build_portfolio_summary(db_session, year=None)
    assert summary.margin_split.no_data == 1
    assert summary.margin_split.avg_margin is None


@pytest.mark.asyncio
async def test_spend_by_client_groups_and_names(db_session):
    client = ClientDB(name="Acme Foundation", slug="acme-foundation")
    db_session.add(client)
    await db_session.flush()
    await _project(db_session, name="P1", start_date=date(2021, 1, 1), client_id=client.id)
    summary = await build_portfolio_summary(db_session, year=None)
    # No reports => total_cost 0, but the client still appears with project_count 1.
    names = {c.client_name for c in summary.spend_by_client}
    assert "Acme Foundation" in names


@pytest.mark.asyncio
async def test_breakdowns_present_but_empty_when_no_tags(db_session):
    summary = await build_portfolio_summary(db_session, year=None)
    slugs = {b.taxonomy_slug for b in summary.breakdowns}
    assert slugs <= {"impact-area", "service"}
    for b in summary.breakdowns:
        assert b.terms == []


@pytest.mark.asyncio
async def test_rateless_currency_excluded_from_total_spend(db_session):
    """A project whose currency has no exchange rate must be excluded from
    total_spend_eur (not counted as 0 or as its raw cost value).

    No ExchangeRateDB row for "GBP" is seeded, so _to_eur returns None for
    that project and its cost must not appear in total_spend_eur.
    """
    eur_project = await _project(
        db_session, name="EUR project", start_date=date(2023, 1, 1), currency="EUR"
    )
    await _cost_fixtures(
        db_session, eur_project, cost=1000.0, currency="EUR", period_date=date(2024, 1, 1)
    )

    gbp_project = await _project(
        db_session, name="GBP project", start_date=date(2023, 1, 1), currency="GBP"
    )
    await _cost_fixtures(
        db_session, gbp_project, cost=5000.0, currency="GBP", period_date=date(2024, 2, 1)
    )

    summary = await build_portfolio_summary(db_session, year=None)

    # EUR project is convertible: 1000 EUR -> 1000 EUR.
    # GBP project has no rate: excluded (not counted as 0, not counted as 5000).
    assert summary.kpis.project_count == 2
    assert summary.kpis.total_spend_eur == 1000.0


@pytest.mark.asyncio
async def test_real_cost_produces_gain_and_loss_margin(db_session):
    """With real budget + cost data, avg_margin is non-None and
    gain + loss + no_data equals project_count.

    gain project: cost 500 < budget 1000 -> burn 50% -> margin 50 -> gain.
    loss project: cost 1500 > budget 1000 -> burn 150% -> margin -50 -> loss.
    """
    gain_project = await _project(
        db_session,
        name="Under budget",
        start_date=date(2023, 1, 1),
        budget=Decimal("1000"),
        currency="EUR",
        is_billable=True,
        is_absence=False,
    )
    await _cost_fixtures(db_session, gain_project, cost=500.0, period_date=date(2023, 1, 1))

    loss_project = await _project(
        db_session,
        name="Over budget",
        start_date=date(2023, 6, 1),
        budget=Decimal("1000"),
        currency="EUR",
        is_billable=True,
        is_absence=False,
    )
    await _cost_fixtures(db_session, loss_project, cost=1500.0, period_date=date(2023, 2, 1))

    summary = await build_portfolio_summary(db_session, year=None)

    assert summary.kpis.avg_margin is not None
    ms = summary.margin_split
    assert ms.gain + ms.loss + ms.no_data == summary.kpis.project_count
    assert ms.gain >= 1
    assert ms.loss >= 1


@pytest.mark.asyncio
async def test_year_filter_scopes_kpis_not_volume_trend(db_session):
    """year= scopes KPIs (project_count) to active projects in that year,
    but volume_by_year always spans all candidate projects (trend is all-time).
    """
    await _project(
        db_session,
        name="Early project",
        start_date=date(2019, 1, 1),
        end_date=date(2019, 12, 31),
    )
    await _project(
        db_session,
        name="Later project",
        start_date=date(2023, 1, 1),
        end_date=date(2023, 12, 31),
    )

    summary = await build_portfolio_summary(db_session, year=2019)

    # KPIs scoped to 2019: only "Early project" is active that year.
    assert summary.kpis.project_count == 1

    # Volume trend is all-time regardless of year filter.
    trend_years = {v.year for v in summary.volume_by_year}
    assert 2019 in trend_years
    assert 2023 in trend_years
