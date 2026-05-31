"""Tests for accrual budget derivation (FX conversion + line build)."""

from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.project import ProjectDB
from app.modules.accrual.models.accrual_cell import AccrualCellDB
from app.modules.accrual.models.accrual_line import LineSource
from app.modules.accrual.models.accrual_line_project import AccrualLineProjectDB
from app.modules.accrual.models.accrual_period import AccrualPeriodDB
from app.modules.accrual.services import budget_derivation


@pytest.mark.asyncio
async def test_convert_eur_passthrough(db_session: AsyncSession) -> None:
    result = await budget_derivation.convert_original_budget(
        db_session, original_budget=Decimal("1000"), currency="EUR", start_date=date(2026, 3, 1)
    )
    assert result == Decimal("1000.00")


@pytest.mark.asyncio
async def test_convert_uses_period_rate(db_session: AsyncSession) -> None:
    db_session.add(
        AccrualPeriodDB(start_date=date(2026, 1, 1), status="open", fx_rates={"USD": "1.25"})
    )
    await db_session.flush()
    result = await budget_derivation.convert_original_budget(
        db_session, original_budget=Decimal("1000"), currency="dollar", start_date=date(2026, 6, 1)
    )
    assert result == Decimal("800.00")  # 1000 / 1.25


@pytest.mark.asyncio
async def test_convert_falls_back_to_ecb(db_session: AsyncSession) -> None:
    from app.core.models.exchange_rate import ExchangeRateDB

    db_session.add(AccrualPeriodDB(start_date=date(2026, 1, 1), status="open", fx_rates={}))
    db_session.add(
        ExchangeRateDB(rate_date=date(2026, 1, 15), currency_code="USD", rate=Decimal("1.10"))
    )
    await db_session.flush()
    result = await budget_derivation.convert_original_budget(
        db_session, original_budget=Decimal("1100"), currency="USD", start_date=date(2026, 6, 1)
    )
    assert result == Decimal("1000.00")  # 1100 / 1.10


@pytest.mark.asyncio
async def test_convert_returns_none_when_no_rate(db_session: AsyncSession) -> None:
    result = await budget_derivation.convert_original_budget(
        db_session, original_budget=Decimal("1000"), currency="ZWL", start_date=date(2026, 6, 1)
    )
    assert result is None


async def _make_project(db: AsyncSession, **kw) -> ProjectDB:
    defaults = dict(
        name="P",
        code="P.1",
        currency="dollar",
        budget=None,
        original_budget=Decimal("1000"),
        start_date=date(2026, 1, 1),
        end_date=date(2026, 4, 1),
    )
    defaults.update(kw)
    p = ProjectDB(**defaults)
    db.add(p)
    await db.flush()
    return p


@pytest.mark.asyncio
async def test_upsert_creates_team_budget_line_with_spread(db_session: AsyncSession) -> None:
    db_session.add(
        AccrualPeriodDB(start_date=date(2026, 1, 1), status="open", fx_rates={"USD": "1.00"})
    )
    project = await _make_project(db_session)  # 4 months, 1000 USD @ 1.00 -> 1000 EUR
    line = await budget_derivation.upsert_derived_line(db_session, project_id=project.id)
    assert line is not None
    assert line.source == LineSource.TEAM_BUDGET.value
    assert line.value_eur == Decimal("1000.00")
    assert line.currency == "USD"
    assert line.rate == Decimal("1.00")
    assert line.window_start == date(2026, 1, 1)
    assert line.window_end == date(2026, 4, 1)
    cells = (
        (await db_session.execute(select(AccrualCellDB).where(AccrualCellDB.line_id == line.id)))
        .scalars()
        .all()
    )
    assert len(cells) == 4  # Jan..Apr inclusive
    assert sum(c.amount for c in cells) == Decimal("1000.00")
    link = (
        await db_session.execute(
            select(AccrualLineProjectDB).where(AccrualLineProjectDB.line_id == line.id)
        )
    ).scalar_one()
    assert link.project_id == project.id


@pytest.mark.asyncio
async def test_upsert_noop_when_not_derivable(db_session: AsyncSession) -> None:
    project = await _make_project(db_session, original_budget=None)
    assert await budget_derivation.upsert_derived_line(db_session, project_id=project.id) is None


@pytest.mark.asyncio
async def test_upsert_noop_when_no_rate(db_session: AsyncSession) -> None:
    # CAD passes the projects currency CHECK constraint but has no FX rate seeded
    # in this test DB, so the line is non-derivable -> no-op.
    project = await _make_project(db_session, currency="CAD")
    assert await budget_derivation.upsert_derived_line(db_session, project_id=project.id) is None


@pytest.mark.asyncio
async def test_update_redistributes_open_months_keeps_window(db_session: AsyncSession) -> None:
    db_session.add(
        AccrualPeriodDB(start_date=date(2026, 1, 1), status="open", fx_rates={"USD": "1.00"})
    )
    project = await _make_project(db_session)
    line = await budget_derivation.upsert_derived_line(db_session, project_id=project.id)
    # Budget doubles (original_budget 1000 -> 2000); window must NOT change.
    project.original_budget = Decimal("2000")
    await db_session.flush()
    refreshed = await budget_derivation.upsert_derived_line(db_session, project_id=project.id)
    assert refreshed.id == line.id
    assert refreshed.value_eur == Decimal("2000.00")
    assert refreshed.window_start == date(2026, 1, 1)
    assert refreshed.window_end == date(2026, 4, 1)
    cells = (
        (await db_session.execute(select(AccrualCellDB).where(AccrualCellDB.line_id == line.id)))
        .scalars()
        .all()
    )
    assert sum(c.amount for c in cells) == Decimal("2000.00")


@pytest.mark.asyncio
async def test_update_does_not_touch_frozen_cells(db_session: AsyncSession) -> None:
    from app.core.models.exchange_rate import ExchangeRateDB

    db_session.add(
        AccrualPeriodDB(start_date=date(2026, 3, 1), status="open", fx_rates={"USD": "1.00"})
    )
    # Project starts Jan 2026 (before the open period) — its conversion rate is
    # resolved via ECB at start_date, so seed a USD rate effective then.
    db_session.add(
        ExchangeRateDB(rate_date=date(2026, 1, 1), currency_code="USD", rate=Decimal("1.00"))
    )
    project = await _make_project(db_session)
    line = await budget_derivation.upsert_derived_line(db_session, project_id=project.id)
    # Freeze Jan + Feb (before the open period) at 250 each.
    frozen = (
        (
            await db_session.execute(
                select(AccrualCellDB).where(
                    AccrualCellDB.line_id == line.id, AccrualCellDB.month.in_([1, 2])
                )
            )
        )
        .scalars()
        .all()
    )
    for c in frozen:
        c.is_frozen = True
        c.frozen_at = datetime.now(UTC)
        c.frozen_eur_amount = c.amount
    await db_session.flush()
    frozen_total = sum(c.amount for c in frozen)
    project.original_budget = Decimal("2000")
    await db_session.flush()
    await budget_derivation.upsert_derived_line(db_session, project_id=project.id)
    still_frozen = (
        (
            await db_session.execute(
                select(AccrualCellDB).where(
                    AccrualCellDB.line_id == line.id, AccrualCellDB.is_frozen.is_(True)
                )
            )
        )
        .scalars()
        .all()
    )
    assert sum(c.amount for c in still_frozen) == frozen_total  # untouched
