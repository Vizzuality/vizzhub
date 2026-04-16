"""Tests for tracker Pydantic schemas."""

import datetime as dt
from decimal import Decimal
from uuid import uuid4

import pytest
from pydantic import ValidationError

from app.modules.tracker.schemas.reporting_period import (
    ReportingPeriodCreate,
    ReportingPeriodResponse,
    ReportingPeriodUpdate,
)
from app.modules.tracker.schemas.report import ReportCreate, ReportResponse
from app.modules.tracker.schemas.report_part import (
    ReportPartCreate,
    ReportPartResponse,
)


class TestReportingPeriodSchemas:
    def test_create_with_defaults(self):
        schema = ReportingPeriodCreate(date=dt.date(2026, 3, 1))
        assert schema.date == dt.date(2026, 3, 1)
        assert schema.base_rate == Decimal("175.00")

    def test_create_with_custom_base_rate(self):
        schema = ReportingPeriodCreate(
            date=dt.date(2026, 3, 1), base_rate=Decimal("190.00"),
        )
        assert schema.base_rate == Decimal("190.00")

    def test_create_rejects_negative_base_rate(self):
        with pytest.raises(ValidationError):
            ReportingPeriodCreate(
                date=dt.date(2026, 3, 1), base_rate=Decimal("-1"),
            )

    def test_update_all_optional(self):
        schema = ReportingPeriodUpdate()
        assert schema.date is None
        assert schema.base_rate is None

    def test_response_serializes_decimal_as_float(self):
        now = dt.datetime.now(tz=dt.timezone.utc)
        schema = ReportingPeriodResponse(
            id=uuid4(),
            date=dt.date(2026, 3, 1),
            base_rate=175.0,
            status="unstarted",
            created_at=now,
            updated_at=now,
        )
        data = schema.model_dump()
        assert isinstance(data["base_rate"], float)


class TestReportSchemas:
    def test_create_with_defaults(self):
        schema = ReportCreate(
            reporting_period_id=uuid4(),
        )
        assert schema.estimated is True

    def test_create_with_estimated(self):
        schema = ReportCreate(
            reporting_period_id=uuid4(), estimated=True,
        )
        assert schema.estimated is True


class TestReportPartSchemas:
    def test_create_valid(self):
        schema = ReportPartCreate(
            report_id=uuid4(),
            project_id=uuid4(),
            percentage=Decimal("0.20"),
        )
        assert schema.percentage == Decimal("0.20")
        assert schema.functional_area_id is None

    def test_create_rejects_percentage_over_1(self):
        with pytest.raises(ValidationError):
            ReportPartCreate(
                report_id=uuid4(),
                project_id=uuid4(),
                percentage=Decimal("1.5"),
            )

    def test_create_rejects_negative_percentage(self):
        with pytest.raises(ValidationError):
            ReportPartCreate(
                report_id=uuid4(),
                project_id=uuid4(),
                percentage=Decimal("-0.1"),
            )

    def test_response_serializes_decimals(self):
        now = dt.datetime.now(tz=dt.timezone.utc)
        schema = ReportPartResponse(
            id=uuid4(),
            report_id=uuid4(),
            project_id=uuid4(),
            functional_area_id=None,
            percentage=0.2,
            days=0.0296,
            cost=2274.02,
            created_at=now,
            updated_at=now,
        )
        data = schema.model_dump()
        assert isinstance(data["cost"], float)
        assert isinstance(data["days"], float)
