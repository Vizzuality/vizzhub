"""Tests for mcp_server.data.tracker — project and cost queries."""

from datetime import date
from decimal import Decimal
from uuid import uuid4

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.models.functional_area import FunctionalAreaDB
from app.core.models.project import ProjectDB
from app.core.models.user import UserDB
from app.modules.tracker.models import (
    BudgetLineDB,
    InvoiceDB,
    NonStaffCostDB,
    ProgressReportDB,
    ReportDB,
    ReportPartDB,
    ReportingPeriodDB,
    TrackerProjectSettingsDB,
)
from app.modules.tracker.models.postponement import InvoicePostponementDB


@pytest_asyncio.fixture
async def fa_backend(db_session: AsyncSession) -> FunctionalAreaDB:
    fa = FunctionalAreaDB(name="Backend")
    db_session.add(fa)
    await db_session.flush()
    return fa


@pytest_asyncio.fixture
async def fa_frontend(db_session: AsyncSession) -> FunctionalAreaDB:
    fa = FunctionalAreaDB(name="Frontend")
    db_session.add(fa)
    await db_session.flush()
    return fa


@pytest_asyncio.fixture
async def user_alice(db_session: AsyncSession, fa_backend: FunctionalAreaDB) -> UserDB:
    user = UserDB(
        email="alice@vizzuality.com",
        first_name="Alice",
        last_name="Smith",
        functional_area_id=fa_backend.id,
        active=True,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def user_bob(db_session: AsyncSession, fa_frontend: FunctionalAreaDB) -> UserDB:
    user = UserDB(
        email="bob@vizzuality.com",
        first_name="Bob",
        last_name="Jones",
        functional_area_id=fa_frontend.id,
        active=True,
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest_asyncio.fixture
async def project_acorn(
    db_session: AsyncSession, user_alice: UserDB,
) -> ProjectDB:
    project = ProjectDB(
        name="Acorn",
        code="ACR",
        status="live",
        is_billable=True,
        currency="euro",
        budget=Decimal("100000.00"),
        start_date=date(2026, 1, 1),
        end_date=date(2026, 12, 31),
        project_manager_id=user_alice.id,
    )
    db_session.add(project)
    await db_session.flush()
    return project


@pytest_asyncio.fixture
async def project_birch(db_session: AsyncSession) -> ProjectDB:
    project = ProjectDB(
        name="Birch",
        code="BRC",
        status="proposal",
        is_billable=False,
        currency="dollar",
        budget=None,
    )
    db_session.add(project)
    await db_session.flush()
    return project


@pytest_asyncio.fixture
async def absence_project(db_session: AsyncSession) -> ProjectDB:
    project = ProjectDB(
        name="Holidays",
        code="HOL",
        status="live",
        is_billable=False,
        is_absence=True,
    )
    db_session.add(project)
    await db_session.flush()
    return project


@pytest_asyncio.fixture
async def period_jan(db_session: AsyncSession) -> ReportingPeriodDB:
    period = ReportingPeriodDB(
        date=date(2026, 1, 1),
        status="finished",
        base_rate=Decimal("175.00"),
    )
    db_session.add(period)
    await db_session.flush()
    return period


@pytest_asyncio.fixture
async def period_feb(db_session: AsyncSession) -> ReportingPeriodDB:
    period = ReportingPeriodDB(
        date=date(2026, 2, 1),
        status="active",
        base_rate=Decimal("175.00"),
    )
    db_session.add(period)
    await db_session.flush()
    return period


@pytest_asyncio.fixture
async def seed_reports(
    db_session: AsyncSession,
    project_acorn: ProjectDB,
    user_alice: UserDB,
    user_bob: UserDB,
    fa_backend: FunctionalAreaDB,
    fa_frontend: FunctionalAreaDB,
    period_jan: ReportingPeriodDB,
    period_feb: ReportingPeriodDB,
) -> None:
    """Create confirmed reports with parts for both users across 2 periods."""
    # Alice Jan: 50% on Acorn (backend)
    report_a_jan = ReportDB(
        user_id=user_alice.id,
        reporting_period_id=period_jan.id,
        estimated=False,
    )
    db_session.add(report_a_jan)
    await db_session.flush()

    db_session.add(ReportPartDB(
        report_id=report_a_jan.id,
        project_id=project_acorn.id,
        functional_area_id=fa_backend.id,
        percentage=Decimal("0.5000"),
        days=Decimal("10.0000"),
        cost=Decimal("5000.00"),
    ))

    # Bob Jan: 30% on Acorn (frontend)
    report_b_jan = ReportDB(
        user_id=user_bob.id,
        reporting_period_id=period_jan.id,
        estimated=False,
    )
    db_session.add(report_b_jan)
    await db_session.flush()

    db_session.add(ReportPartDB(
        report_id=report_b_jan.id,
        project_id=project_acorn.id,
        functional_area_id=fa_frontend.id,
        percentage=Decimal("0.3000"),
        days=Decimal("6.0000"),
        cost=Decimal("3000.00"),
    ))

    # Alice Feb: 40% on Acorn (backend) — estimated (should be excluded from costs)
    report_a_feb = ReportDB(
        user_id=user_alice.id,
        reporting_period_id=period_feb.id,
        estimated=True,
    )
    db_session.add(report_a_feb)
    await db_session.flush()

    db_session.add(ReportPartDB(
        report_id=report_a_feb.id,
        project_id=project_acorn.id,
        functional_area_id=fa_backend.id,
        percentage=Decimal("0.4000"),
        days=Decimal("8.0000"),
        cost=Decimal("4000.00"),
    ))

    await db_session.commit()


# ---- get_projects ----

@pytest.mark.asyncio
async def test_get_projects_returns_non_absence(
    db_session: AsyncSession,
    project_acorn: ProjectDB,
    project_birch: ProjectDB,
    absence_project: ProjectDB,
) -> None:
    await db_session.commit()
    from mcp_server.data.tracker import get_projects

    result = await get_projects(db_session)
    names = [p["name"] for p in result]
    assert "Acorn" in names
    assert "Birch" in names
    assert "Holidays" not in names


@pytest.mark.asyncio
async def test_get_projects_filter_by_status(
    db_session: AsyncSession,
    project_acorn: ProjectDB,
    project_birch: ProjectDB,
) -> None:
    await db_session.commit()
    from mcp_server.data.tracker import get_projects

    result = await get_projects(db_session, status="live")
    assert len(result) == 1
    assert result[0]["name"] == "Acorn"


@pytest.mark.asyncio
async def test_get_projects_includes_cost_summary(
    db_session: AsyncSession,
    project_acorn: ProjectDB,
    seed_reports,
) -> None:
    from mcp_server.data.tracker import get_projects

    result = await get_projects(db_session)
    acorn = next(p for p in result if p["name"] == "Acorn")
    # Only Jan confirmed parts count (5000 + 3000 = 8000 staff)
    assert acorn["staff_cost"] == 8000.0
    assert acorn["total_cost"] == 8000.0
    assert acorn["burn_percentage"] == 8.0  # 8000/100000*100


@pytest.mark.asyncio
async def test_get_projects_includes_income(
    db_session: AsyncSession,
    project_acorn: ProjectDB,
) -> None:
    db_session.add(InvoiceDB(
        project_id=project_acorn.id,
        amount=Decimal("25000.00"),
        due_date=date(2026, 3, 1),
        milestone="M1",
        status="paid",
    ))
    await db_session.commit()
    from mcp_server.data.tracker import get_projects

    result = await get_projects(db_session)
    acorn = next(p for p in result if p["name"] == "Acorn")
    assert acorn["income"] == 25000.0


@pytest.mark.asyncio
async def test_get_projects_shows_pm_name(
    db_session: AsyncSession,
    project_acorn: ProjectDB,
) -> None:
    await db_session.commit()
    from mcp_server.data.tracker import get_projects

    result = await get_projects(db_session)
    acorn = next(p for p in result if p["name"] == "Acorn")
    assert "Alice" in acorn["project_manager"]


# ---- get_project_detail ----

@pytest.mark.asyncio
async def test_get_project_detail_not_found(db_session: AsyncSession) -> None:
    from mcp_server.data.tracker import get_project_detail

    result = await get_project_detail(db_session, uuid4())
    assert result is None


@pytest.mark.asyncio
async def test_get_project_detail_includes_budget_lines(
    db_session: AsyncSession,
    project_acorn: ProjectDB,
    fa_backend: FunctionalAreaDB,
    fa_frontend: FunctionalAreaDB,
) -> None:
    db_session.add_all([
        BudgetLineDB(
            project_id=project_acorn.id,
            functional_area_id=fa_backend.id,
            days=Decimal("60.00"),
        ),
        BudgetLineDB(
            project_id=project_acorn.id,
            functional_area_id=fa_frontend.id,
            days=Decimal("40.00"),
        ),
    ])
    await db_session.commit()
    from mcp_server.data.tracker import get_project_detail

    result = await get_project_detail(db_session, project_acorn.id)
    assert result is not None
    assert len(result["budget_lines"]) == 2
    fa_names = [bl["functional_area"] for bl in result["budget_lines"]]
    assert "Backend" in fa_names


@pytest.mark.asyncio
async def test_get_project_detail_cost_summary(
    db_session: AsyncSession,
    project_acorn: ProjectDB,
    seed_reports,
) -> None:
    # Add non-staff cost
    from mcp_server.data.tracker import get_project_detail

    db_session.add(NonStaffCostDB(
        project_id=project_acorn.id,
        reporting_period_id=(await db_session.execute(
            __import__("sqlalchemy").select(ReportingPeriodDB.id)
            .where(ReportingPeriodDB.date == date(2026, 1, 1))
        )).scalar_one(),
        cost=Decimal("2000.00"),
        cost_type="servers",
    ))
    await db_session.commit()

    result = await get_project_detail(db_session, project_acorn.id)
    cs = result["cost_summary"]
    assert cs["staff_cost"] == 8000.0
    assert cs["non_staff_cost"] == 2000.0
    assert cs["total_cost"] == 10000.0
    assert cs["burn_percentage"] == 10.0
    assert len(cs["periods"]) >= 1


@pytest.mark.asyncio
async def test_get_project_detail_contract_rate(
    db_session: AsyncSession,
    project_acorn: ProjectDB,
) -> None:
    db_session.add(TrackerProjectSettingsDB(
        project_id=project_acorn.id,
        contract_rate=Decimal("200.00"),
    ))
    await db_session.commit()
    from mcp_server.data.tracker import get_project_detail

    result = await get_project_detail(db_session, project_acorn.id)
    assert result["contract_rate"] == 200.0


# ---- get_project_time ----

@pytest.mark.asyncio
async def test_get_project_time_by_user(
    db_session: AsyncSession,
    project_acorn: ProjectDB,
    seed_reports,
) -> None:
    from mcp_server.data.tracker import get_project_time

    result = await get_project_time(db_session, project_acorn.id, group_by="user")
    assert len(result) == 2
    names = [r["name"] for r in result]
    assert any("Alice" in n for n in names)
    # Sorted by total_days desc: Alice (10) > Bob (6)
    assert result[0]["total_days"] == 10.0


@pytest.mark.asyncio
async def test_get_project_time_by_functional_area(
    db_session: AsyncSession,
    project_acorn: ProjectDB,
    seed_reports,
) -> None:
    from mcp_server.data.tracker import get_project_time

    result = await get_project_time(db_session, project_acorn.id, group_by="functional_area")
    assert len(result) == 2
    names = [r["name"] for r in result]
    assert "Backend" in names
    assert "Frontend" in names


@pytest.mark.asyncio
async def test_get_project_time_excludes_estimated(
    db_session: AsyncSession,
    project_acorn: ProjectDB,
    seed_reports,
) -> None:
    from mcp_server.data.tracker import get_project_time

    result = await get_project_time(db_session, project_acorn.id, group_by="user")
    alice = next(r for r in result if "Alice" in r["name"])
    # Only Jan (10 days), Feb estimated is excluded
    assert alice["total_days"] == 10.0
    assert len(alice["periods"]) == 1


# ---- get_project_invoices ----

@pytest.mark.asyncio
async def test_get_project_invoices_effective_status(
    db_session: AsyncSession,
    project_acorn: ProjectDB,
) -> None:
    # Paid invoice
    db_session.add(InvoiceDB(
        project_id=project_acorn.id,
        amount=Decimal("10000.00"),
        due_date=date(2026, 1, 15),
        milestone="M1",
        status="paid",
    ))
    # Scheduled but past due -> should be pending_to_issue
    db_session.add(InvoiceDB(
        project_id=project_acorn.id,
        amount=Decimal("15000.00"),
        due_date=date(2025, 12, 1),
        milestone="M2",
        status="scheduled",
    ))
    await db_session.commit()
    from mcp_server.data.tracker import get_project_invoices

    result = await get_project_invoices(db_session, project_acorn.id)
    assert len(result) == 2

    statuses = {r["milestone"]: r["status"] for r in result}
    assert statuses["M1"] == "paid"
    assert statuses["M2"] == "pending_to_issue"


@pytest.mark.asyncio
async def test_get_project_invoices_postponed(
    db_session: AsyncSession,
    project_acorn: ProjectDB,
    user_alice: UserDB,
) -> None:
    invoice = InvoiceDB(
        project_id=project_acorn.id,
        amount=Decimal("20000.00"),
        due_date=date(2026, 3, 1),
        milestone="M3",
        status="scheduled",
    )
    db_session.add(invoice)
    await db_session.flush()

    db_session.add(InvoicePostponementDB(
        invoice_id=invoice.id,
        postponed_to=date(2099, 12, 31),
        reason="Client delay",
        created_by=user_alice.id,
    ))
    await db_session.commit()
    from mcp_server.data.tracker import get_project_invoices

    result = await get_project_invoices(db_session, project_acorn.id)
    m3 = next(r for r in result if r["milestone"] == "M3")
    assert m3["status"] == "postponed"
    assert m3["postpone_count"] == 1


@pytest.mark.asyncio
async def test_get_project_invoices_empty(
    db_session: AsyncSession,
    project_acorn: ProjectDB,
) -> None:
    await db_session.commit()
    from mcp_server.data.tracker import get_project_invoices

    result = await get_project_invoices(db_session, project_acorn.id)
    assert result == []


# ---- get_project_progress ----

@pytest.mark.asyncio
async def test_get_project_progress(
    db_session: AsyncSession,
    project_acorn: ProjectDB,
    period_jan: ReportingPeriodDB,
    period_feb: ReportingPeriodDB,
) -> None:
    db_session.add_all([
        ProgressReportDB(
            reporting_period_id=period_jan.id,
            project_id=project_acorn.id,
            percentage=Decimal("0.2500"),
            delta=Decimal("0.2500"),
        ),
        ProgressReportDB(
            reporting_period_id=period_feb.id,
            project_id=project_acorn.id,
            percentage=Decimal("0.4000"),
            delta=Decimal("0.1500"),
        ),
    ])
    await db_session.commit()
    from mcp_server.data.tracker import get_project_progress

    result = await get_project_progress(db_session, project_acorn.id)
    assert len(result) == 2
    # Newest first
    assert result[0]["percentage"] == 0.4
    assert result[1]["percentage"] == 0.25
    assert result[1]["delta"] == 0.25


# ---- get_periods ----

@pytest.mark.asyncio
async def test_get_periods_returns_all(
    db_session: AsyncSession,
    period_jan: ReportingPeriodDB,
    period_feb: ReportingPeriodDB,
) -> None:
    await db_session.commit()
    from mcp_server.data.tracker import get_periods

    result = await get_periods(db_session)
    assert len(result) == 2
    # Newest first
    assert result[0]["date"] == date(2026, 2, 1)


@pytest.mark.asyncio
async def test_get_periods_filter_by_status(
    db_session: AsyncSession,
    period_jan: ReportingPeriodDB,
    period_feb: ReportingPeriodDB,
) -> None:
    await db_session.commit()
    from mcp_server.data.tracker import get_periods

    result = await get_periods(db_session, status="active")
    assert len(result) == 1
    assert result[0]["status"] == "active"


@pytest.mark.asyncio
async def test_get_periods_report_counts(
    db_session: AsyncSession,
    period_jan: ReportingPeriodDB,
    user_alice: UserDB,
    user_bob: UserDB,
) -> None:
    # 2 reports in Jan: 1 confirmed, 1 estimated
    db_session.add(ReportDB(
        user_id=user_alice.id,
        reporting_period_id=period_jan.id,
        estimated=False,
    ))
    db_session.add(ReportDB(
        user_id=user_bob.id,
        reporting_period_id=period_jan.id,
        estimated=True,
    ))
    await db_session.commit()
    from mcp_server.data.tracker import get_periods

    result = await get_periods(db_session)
    jan = result[0]
    assert jan["report_count"] == 2
    assert jan["confirmed_count"] == 1
