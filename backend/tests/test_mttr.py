"""Tests for mttr (Mean Time To Repair) indicator.

Tests cover:
- Collection from Jira API
- Business hours calculation
- Edge cases (no incidents, missing dates)
"""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from app.services.collectors.jira.mttr import (
    _business_hours_diff,
    _parse_jira_datetime,
    collect_mttr,
)


class TestCollectMTTR:
    """Test collect_mttr function."""

    @pytest.mark.asyncio
    async def test_collect_mttr_calls_correct_jql(self) -> None:
        """Should query incidents and high-priority bugs."""
        mock_client = AsyncMock()
        mock_client.search_issues = AsyncMock(return_value=[])

        await collect_mttr(mock_client, "PROJ")

        mock_client.search_issues.assert_called_once()
        call_args = mock_client.search_issues.call_args
        jql = call_args[0][1]

        assert "statusCategory = Done" in jql
        assert "type = Incident" in jql
        assert "type = Bug" in jql
        assert "priority IN" in jql

    @pytest.mark.asyncio
    async def test_collect_mttr_no_incidents(self) -> None:
        """Should return None when no incidents found."""
        mock_client = AsyncMock()
        mock_client.search_issues = AsyncMock(return_value=[])

        result = await collect_mttr(mock_client, "TEST")

        assert result["incidents_count"] == 0
        assert result["mttr_hours"] is None

    @pytest.mark.asyncio
    async def test_collect_mttr_calculates_average(self) -> None:
        """Should calculate average resolution time."""
        mock_client = AsyncMock()
        mock_client.search_issues = AsyncMock(return_value=[
            {
                "fields": {
                    "created": "2026-01-20T09:00:00+00:00",
                    "resolutiondate": "2026-01-20T17:00:00+00:00",
                }
            },
            {
                "fields": {
                    "created": "2026-01-20T09:00:00+00:00",
                    "resolutiondate": "2026-01-20T13:00:00+00:00",
                }
            },
        ])

        result = await collect_mttr(mock_client, "TEST")

        assert result["incidents_count"] == 2
        assert result["mttr_hours"] == 6.0  # (8 + 4) / 2

    @pytest.mark.asyncio
    async def test_collect_mttr_skips_invalid_dates(self) -> None:
        """Should skip issues with missing or invalid dates."""
        mock_client = AsyncMock()
        mock_client.search_issues = AsyncMock(return_value=[
            {"fields": {"created": "2026-01-20T09:00:00+00:00", "resolutiondate": None}},
            {"fields": {"created": None, "resolutiondate": "2026-01-20T17:00:00+00:00"}},
            {
                "fields": {
                    "created": "2026-01-20T09:00:00+00:00",
                    "resolutiondate": "2026-01-20T17:00:00+00:00",
                }
            },
        ])

        result = await collect_mttr(mock_client, "TEST")

        assert result["incidents_count"] == 1
        assert result["mttr_hours"] == 8.0


class TestParseJiraDatetime:
    """Test datetime parsing."""

    def test_parse_iso_format(self) -> None:
        """Should parse ISO format with timezone."""
        result = _parse_jira_datetime("2026-01-20T10:30:00+00:00")
        assert result == datetime(2026, 1, 20, 10, 30, 0, tzinfo=timezone.utc)

    def test_parse_z_suffix(self) -> None:
        """Should handle Z suffix."""
        result = _parse_jira_datetime("2026-01-20T10:30:00Z")
        assert result == datetime(2026, 1, 20, 10, 30, 0, tzinfo=timezone.utc)

    def test_parse_none(self) -> None:
        """Should return None for None input."""
        assert _parse_jira_datetime(None) is None

    def test_parse_empty_string(self) -> None:
        """Should return None for empty string."""
        assert _parse_jira_datetime("") is None

    def test_parse_invalid_format(self) -> None:
        """Should return None for invalid format."""
        assert _parse_jira_datetime("not-a-date") is None


class TestBusinessHoursDiff:
    """Test business hours calculation."""

    def test_same_day_business_hours(self) -> None:
        """Should calculate hours within same business day."""
        start = datetime(2026, 1, 20, 9, 0, 0)  # Monday 9am
        end = datetime(2026, 1, 20, 17, 0, 0)    # Monday 5pm
        assert _business_hours_diff(start, end) == 8.0

    def test_partial_day(self) -> None:
        """Should calculate partial day hours."""
        start = datetime(2026, 1, 20, 10, 0, 0)  # Monday 10am
        end = datetime(2026, 1, 20, 14, 0, 0)    # Monday 2pm
        assert _business_hours_diff(start, end) == 4.0

    def test_skip_weekend(self) -> None:
        """Should skip weekend days."""
        start = datetime(2026, 1, 17, 9, 0, 0)   # Friday 9am
        end = datetime(2026, 1, 19, 17, 0, 0)    # Sunday 5pm
        # Only Friday counts (8 hours)
        assert _business_hours_diff(start, end) == 8.0

    def test_multiple_business_days(self) -> None:
        """Should calculate across multiple business days."""
        start = datetime(2026, 1, 20, 9, 0, 0)   # Monday 9am
        end = datetime(2026, 1, 21, 17, 0, 0)    # Tuesday 5pm
        assert _business_hours_diff(start, end) == 16.0

    def test_end_before_start(self) -> None:
        """Should return 0 if end is before start."""
        start = datetime(2026, 1, 20, 17, 0, 0)
        end = datetime(2026, 1, 20, 9, 0, 0)
        assert _business_hours_diff(start, end) == 0.0

    def test_outside_business_hours(self) -> None:
        """Should handle times outside business hours."""
        start = datetime(2026, 1, 20, 6, 0, 0)   # Monday 6am (before business)
        end = datetime(2026, 1, 20, 10, 0, 0)    # Monday 10am
        # Only 9am-10am counts = 1 hour
        assert _business_hours_diff(start, end) == 1.0
