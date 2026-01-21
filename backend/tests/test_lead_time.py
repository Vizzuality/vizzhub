"""Tests for lead_time indicator.

Tests cover:
- Collection from Jira API
- Business days calculation
- Edge cases (no issues, missing dates)
"""

from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from app.services.collectors.jira.lead_time import (
    _business_days_diff,
    collect_lead_time,
)


class TestCollectLeadTime:
    """Test collect_lead_time function."""

    @pytest.mark.asyncio
    async def test_collect_lead_time_calls_correct_jql(self) -> None:
        """Should query resolved issues from last 90 days."""
        mock_client = AsyncMock()
        mock_client.search_issues = AsyncMock(return_value=[])

        await collect_lead_time(mock_client, "PROJ")

        mock_client.search_issues.assert_called_once()
        call_args = mock_client.search_issues.call_args
        jql = call_args[0][1]

        assert "statusCategory = Done" in jql
        assert "resolutiondate >= -90d" in jql
        assert "type IN (Story, Task, Bug)" in jql

    @pytest.mark.asyncio
    async def test_collect_lead_time_no_issues(self) -> None:
        """Should return None when no issues found."""
        mock_client = AsyncMock()
        mock_client.search_issues = AsyncMock(return_value=[])

        result = await collect_lead_time(mock_client, "TEST")

        assert result["lead_time_days"] is None
        assert result["sample_size"] == 0

    @pytest.mark.asyncio
    async def test_collect_lead_time_calculates_average(self) -> None:
        """Should calculate average lead time in business days."""
        mock_client = AsyncMock()
        mock_client.search_issues = AsyncMock(return_value=[
            {
                "fields": {
                    "created": "2026-01-20T09:00:00+00:00",  # Monday
                    "resolutiondate": "2026-01-20T18:00:00+00:00",  # Same day
                }
            },
            {
                "fields": {
                    "created": "2026-01-20T09:00:00+00:00",  # Monday
                    "resolutiondate": "2026-01-21T18:00:00+00:00",  # Tuesday
                }
            },
        ])

        result = await collect_lead_time(mock_client, "TEST")

        assert result["sample_size"] == 2
        assert result["lead_time_days"] is not None
        # (1 day + 2 days) / 2 = 1.5 days average
        assert result["lead_time_days"] == 1.5

    @pytest.mark.asyncio
    async def test_collect_lead_time_skips_invalid_dates(self) -> None:
        """Should skip issues with missing dates."""
        mock_client = AsyncMock()
        mock_client.search_issues = AsyncMock(return_value=[
            {"fields": {"created": "2026-01-20T09:00:00+00:00", "resolutiondate": None}},
            {
                "fields": {
                    "created": "2026-01-20T09:00:00+00:00",
                    "resolutiondate": "2026-01-20T18:00:00+00:00",
                }
            },
        ])

        result = await collect_lead_time(mock_client, "TEST")

        assert result["sample_size"] == 1


class TestBusinessDaysDiff:
    """Test business days calculation."""

    def test_same_day(self) -> None:
        """Should calculate fraction of a day."""
        start = datetime(2026, 1, 20, 9, 0, 0)   # Monday 9am
        end = datetime(2026, 1, 20, 18, 0, 0)    # Monday 6pm
        assert _business_days_diff(start, end) == 1.0

    def test_two_business_days(self) -> None:
        """Should calculate two full business days."""
        start = datetime(2026, 1, 20, 9, 0, 0)   # Monday 9am
        end = datetime(2026, 1, 21, 18, 0, 0)    # Tuesday 6pm
        assert _business_days_diff(start, end) == 2.0

    def test_skip_weekend(self) -> None:
        """Should skip weekend days."""
        start = datetime(2026, 1, 17, 9, 0, 0)   # Friday 9am
        end = datetime(2026, 1, 19, 18, 0, 0)    # Sunday 6pm
        # Only Friday counts = 1 day
        assert _business_days_diff(start, end) == 1.0

    def test_week_with_weekend(self) -> None:
        """Should calculate business days across weekend."""
        start = datetime(2026, 1, 17, 9, 0, 0)   # Friday 9am
        end = datetime(2026, 1, 20, 18, 0, 0)    # Monday 6pm
        # Friday + Monday = 2 days
        assert _business_days_diff(start, end) == 2.0

    def test_end_before_start(self) -> None:
        """Should return 0 if end is before start."""
        start = datetime(2026, 1, 20, 18, 0, 0)
        end = datetime(2026, 1, 20, 9, 0, 0)
        assert _business_days_diff(start, end) == 0.0
