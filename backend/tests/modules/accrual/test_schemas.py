"""Unit tests for accrual Pydantic schemas."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from app.modules.accrual.schemas import (
    BulkCellsRequest,
    BulkCellUpdate,
    CellUpdate,
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
