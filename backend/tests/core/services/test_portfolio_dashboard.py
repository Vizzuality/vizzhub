"""Unit tests for the portfolio analytics dashboard service."""

from datetime import date

import pytest

from app.core.models.client import ClientDB
from app.core.models.project import ProjectDB
from app.core.services.portfolio_dashboard import build_portfolio_summary


async def _project(db, **kw):
    defaults = dict(is_billable=True, is_absence=False, status="live", currency="EUR")
    defaults.update(kw)
    p = ProjectDB(**defaults)
    db.add(p)
    await db.flush()
    return p


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
