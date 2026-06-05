"""Tests for the project→accrual provisioning orchestrator."""

import re
from datetime import date
from decimal import Decimal
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.project import ProjectDB
from app.core.services import project_provisioning
from app.modules.accrual.models.accrual_line import AccrualLineDB, LineSource
from app.modules.accrual.models.accrual_line_project import AccrualLineProjectDB
from app.modules.accrual.models.accrual_period import AccrualPeriodDB
from app.modules.accrual.services import cell_service


@pytest.mark.asyncio
async def test_provision_derives_budget_and_builds_line(db_session: AsyncSession) -> None:
    db_session.add(
        AccrualPeriodDB(start_date=date(2026, 1, 1), status="open", fx_rates={"USD": "1.25"})
    )
    project = ProjectDB(
        name="P",
        code="P.1",
        currency="dollar",
        budget=None,
        original_budget=Decimal("1000"),
        start_date=date(2026, 1, 1),
        end_date=date(2026, 4, 1),
    )
    db_session.add(project)
    await db_session.flush()
    result = await project_provisioning.provision_project_accrual(db_session, project=project)
    assert project.budget == Decimal("800.00")  # 1000 / 1.25
    assert result.budget_changed is True
    assert result.line_id is not None
    line = await db_session.get(AccrualLineDB, result.line_id)
    assert line.value_eur == Decimal("800.00")


@pytest.mark.asyncio
async def test_provision_noop_without_original_budget(db_session: AsyncSession) -> None:
    project = ProjectDB(
        name="P",
        code="P.2",
        currency="dollar",
        budget=Decimal("500"),
        original_budget=None,
        start_date=date(2026, 1, 1),
        end_date=date(2026, 4, 1),
    )
    db_session.add(project)
    await db_session.flush()
    result = await project_provisioning.provision_project_accrual(db_session, project=project)
    assert project.budget == Decimal("500")  # untouched
    assert result.budget_changed is False
    assert result.line_id is None
    lines = (await db_session.execute(select(AccrualLineDB))).scalars().all()
    assert lines == []


@pytest.mark.asyncio
async def test_provision_uses_override_for_project_budget(db_session: AsyncSession) -> None:
    db_session.add(
        AccrualPeriodDB(start_date=date(2026, 1, 1), status="open", fx_rates={"USD": "1.00"})
    )
    project = ProjectDB(
        name="P",
        code="P.4",
        currency="dollar",
        budget=None,
        original_budget=Decimal("1080"),
        start_date=date(2026, 1, 1),
        end_date=date(2026, 3, 31),
    )
    db_session.add(project)
    await db_session.flush()

    # First provision: builds the derived line (value_eur = 1080 / 1.00 = 1080).
    await project_provisioning.provision_project_accrual(db_session, project=project)

    line = (
        (
            await db_session.execute(
                select(AccrualLineDB)
                .join(AccrualLineProjectDB, AccrualLineProjectDB.line_id == AccrualLineDB.id)
                .where(
                    AccrualLineProjectDB.project_id == project.id,
                    AccrualLineDB.source == LineSource.TEAM_BUDGET.value,
                )
            )
        )
        .scalars()
        .first()
    )
    assert line is not None

    # CEO pins an override rate.
    await cell_service.set_line_rate(db_session, line_id=line.id, rate=Decimal("1.08"))
    await db_session.refresh(line)
    assert line.value_eur == Decimal("1000.00")  # 1080 / 1.08

    # Re-provision: project.budget must follow the overridden line value.
    await project_provisioning.provision_project_accrual(db_session, project=project)
    await db_session.flush()
    await db_session.refresh(line)
    assert line.value_eur == Decimal("1000.00")
    assert project.budget == Decimal("1000.00")


def test_orchestrator_holds_no_fx_arithmetic() -> None:
    """Framing invariant: core must not import FX/period internals."""
    src = Path("app/core/services/project_provisioning.py").read_text()
    assert "exchange_rate_service" not in src
    assert "accrual_periods" not in src
    assert not re.search(r"\bfx_rates\b", src)
