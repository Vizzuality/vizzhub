"""Unit tests for accrual Pydantic schemas."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.modules.accrual.schemas import (
    BulkCellsRequest,
    BulkCellUpdate,
    CellUpdate,
)
from app.modules.accrual.schemas.accrual_dashboard import (
    DashboardKpis,
    DashboardMonth,
    DashboardSummary,
)


def test_cell_update_rejects_negative_amount() -> None:
    with pytest.raises(ValidationError):
        CellUpdate(amount=Decimal("-1"))


def test_bulk_cell_update_rejects_month_zero() -> None:
    from uuid import uuid4

    with pytest.raises(ValidationError):
        BulkCellUpdate(project_id=uuid4(), year=2026, month=0, amount=Decimal("1"))


def test_bulk_cells_request_accepts_empty_list() -> None:
    request = BulkCellsRequest(updates=[])
    assert request.updates == []


def test_dashboard_summary_serializes_floats() -> None:
    summary = DashboardSummary(
        year=2026,
        available_years=[2025, 2026],
        months=[DashboardMonth(month=1, amount_eur=100.5, status="recognized")],
        kpis=DashboardKpis(
            recognized_ytd_eur=100.5,
            recognized_quarter_eur=100.5,
            contracted_total_eur=1000.0,
            backlog_eur=899.5,
            plan_recognized_pct=12.5,
            recognized_prev_ytd_eur=80.0,
            yoy_pct=25.625,
        ),
    )
    dumped = summary.model_dump()
    assert dumped["months"][0]["amount_eur"] == 100.5
    assert dumped["kpis"]["backlog_eur"] == 899.5
    assert dumped["kpis"]["yoy_pct"] == 25.625
    assert dumped["months"][0]["status"] == "recognized"
