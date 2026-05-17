"""Tests for lead_time indicator.

Tests cover:
- Collection from Jira API using changelog
- Finding first In Progress transition
- Fallback to created date
- Business days calculation
- Edge cases (no issues, missing dates)
"""

from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from app.modules.scorecard.services.collectors.jira.lead_time import (
    _find_first_in_progress,
    collect_lead_time,
)
from app.modules.scorecard.services.collectors.jira.utils import business_days_diff


class TestCollectLeadTime:
    """Test collect_lead_time function."""

    @pytest.mark.asyncio
    async def test_collect_lead_time_calls_correct_jql(self) -> None:
        """Should query resolved issues from last 90 days with changelog."""
        mock_client = AsyncMock()
        mock_client.search_issues = AsyncMock(return_value=[])

        await collect_lead_time(mock_client, "PROJ")

        mock_client.search_issues.assert_called_once()
        call_args = mock_client.search_issues.call_args
        jql = call_args[0][1]

        assert "statusCategory = Done" in jql
        assert "type IN (Story, Task, Bug)" in jql
        assert call_args.kwargs.get("expand") == ["changelog"]

    @pytest.mark.asyncio
    async def test_collect_lead_time_no_issues(self) -> None:
        """Should return None when no issues found."""
        mock_client = AsyncMock()
        mock_client.search_issues = AsyncMock(return_value=[])

        result = await collect_lead_time(mock_client, "TEST")

        assert result["lead_time_days"] is None
        assert result["sample_size"] == 0

    @pytest.mark.asyncio
    async def test_collect_lead_time_uses_in_progress_from_changelog(self) -> None:
        """Should use first In Progress transition from changelog."""
        mock_client = AsyncMock()
        mock_client.search_issues = AsyncMock(
            return_value=[
                {
                    "fields": {
                        "created": "2026-01-15T09:00:00+00:00",  # Created Wednesday
                        "resolutiondate": "2026-01-20T18:00:00+00:00",  # Resolved Monday
                    },
                    "changelog": {
                        "histories": [
                            {
                                "created": "2026-01-17T09:00:00+00:00",  # In Progress Friday
                                "items": [{"field": "status", "toString": "In Progress"}],
                            }
                        ]
                    },
                },
            ]
        )

        result = await collect_lead_time(mock_client, "TEST")

        assert result["sample_size"] == 1
        # Friday to Monday = 2 business days
        assert result["lead_time_days"] == pytest.approx(2.0)

    @pytest.mark.asyncio
    async def test_collect_lead_time_skips_without_in_progress(self) -> None:
        """Should skip issues without In Progress transition (no fallback)."""
        mock_client = AsyncMock()
        mock_client.search_issues = AsyncMock(
            return_value=[
                {
                    "fields": {
                        "created": "2026-01-20T09:00:00+00:00",
                        "resolutiondate": "2026-01-20T18:00:00+00:00",
                    },
                    "changelog": {
                        "histories": []  # No status transitions
                    },
                },
            ]
        )

        result = await collect_lead_time(mock_client, "TEST")

        assert result["sample_size"] == 0
        assert result["lead_time_days"] is None

    @pytest.mark.asyncio
    async def test_collect_lead_time_calculates_median(self) -> None:
        """Should calculate MEDIAN (audit #7) lead time in business days.
        Two-sample median equals mean, so 1 + 2 days → 1.5 either way."""
        mock_client = AsyncMock()
        mock_client.search_issues = AsyncMock(
            return_value=[
                {
                    "fields": {
                        "created": "2026-01-19T09:00:00+00:00",
                        "resolutiondate": "2026-01-20T18:00:00+00:00",
                    },
                    "changelog": {
                        "histories": [
                            {
                                "created": "2026-01-20T09:00:00+00:00",
                                "items": [{"field": "status", "toString": "In Progress"}],
                            }
                        ]
                    },
                },
                {
                    "fields": {
                        "created": "2026-01-19T09:00:00+00:00",
                        "resolutiondate": "2026-01-21T18:00:00+00:00",
                    },
                    "changelog": {
                        "histories": [
                            {
                                "created": "2026-01-20T09:00:00+00:00",
                                "items": [{"field": "status", "toString": "In Progress"}],
                            }
                        ]
                    },
                },
            ]
        )

        result = await collect_lead_time(mock_client, "TEST")

        assert result["sample_size"] == 2
        assert result["lead_time_days"] == pytest.approx(1.5)

    @pytest.mark.asyncio
    async def test_collect_lead_time_median_resists_outlier(self) -> None:
        """Audit #7: one 30-day outlier must not pull the metric like
        the old mean implementation would have."""

        # 4 issues at 1 business day + 1 issue at 30 business days.
        # Mean would be (4 + 30) / 5 = 6.8 (Low). Median is 1 (High).
        def one_day_issue() -> dict:
            return {
                "fields": {
                    "created": "2026-01-19T09:00:00+00:00",
                    "resolutiondate": "2026-01-20T18:00:00+00:00",
                },
                "changelog": {
                    "histories": [
                        {
                            "created": "2026-01-20T09:00:00+00:00",
                            "items": [{"field": "status", "toString": "In Progress"}],
                        }
                    ]
                },
            }

        outlier_issue = {
            "fields": {
                "created": "2026-01-01T09:00:00+00:00",
                # 6 calendar weeks later (~30 business days)
                "resolutiondate": "2026-02-13T18:00:00+00:00",
            },
            "changelog": {
                "histories": [
                    {
                        "created": "2026-01-02T09:00:00+00:00",
                        "items": [{"field": "status", "toString": "In Progress"}],
                    }
                ]
            },
        }

        mock_client = AsyncMock()
        mock_client.search_issues = AsyncMock(
            return_value=[
                one_day_issue(),
                one_day_issue(),
                one_day_issue(),
                one_day_issue(),
                outlier_issue,
            ]
        )

        result = await collect_lead_time(mock_client, "TEST")

        assert result["sample_size"] == 5
        # Median of [1, 1, 1, 1, ~30] = 1
        assert result["lead_time_days"] == pytest.approx(1.0)

    @pytest.mark.asyncio
    async def test_collect_lead_time_skips_invalid_dates(self) -> None:
        """Should skip issues with missing dates or no In Progress."""
        mock_client = AsyncMock()
        mock_client.search_issues = AsyncMock(
            return_value=[
                {"fields": {"created": "2026-01-20T09:00:00+00:00", "resolutiondate": None}},
                {
                    "fields": {
                        "created": "2026-01-19T09:00:00+00:00",
                        "resolutiondate": "2026-01-20T18:00:00+00:00",
                    },
                    "changelog": {
                        "histories": [
                            {
                                "created": "2026-01-20T09:00:00+00:00",
                                "items": [{"field": "status", "toString": "In Progress"}],
                            }
                        ]
                    },
                },
            ]
        )

        result = await collect_lead_time(mock_client, "TEST")

        assert result["sample_size"] == 1


class TestFindFirstInProgress:
    """Test _find_first_in_progress function."""

    def test_finds_in_progress_transition(self) -> None:
        """Should find first In Progress transition."""
        issue = {
            "changelog": {
                "histories": [
                    {
                        "created": "2026-01-20T09:00:00+00:00",
                        "items": [{"field": "status", "toString": "In Progress"}],
                    }
                ]
            }
        }

        result = _find_first_in_progress(issue)

        assert result is not None
        assert result.day == 20

    def test_finds_first_when_multiple_transitions(self) -> None:
        """Should find the earliest In Progress transition."""
        issue = {
            "changelog": {
                "histories": [
                    {
                        "created": "2026-01-22T09:00:00+00:00",
                        "items": [{"field": "status", "toString": "In Progress"}],
                    },
                    {
                        "created": "2026-01-20T09:00:00+00:00",
                        "items": [{"field": "status", "toString": "In Development"}],
                    },
                ]
            }
        }

        result = _find_first_in_progress(issue)

        assert result is not None
        assert result.day == 20  # Should pick the earlier date

    def test_recognizes_various_in_progress_statuses(self) -> None:
        """Should recognize various In Progress status names."""
        for status_name in [
            "In Progress",
            "in development",
            "Development",
            "WIP",
            "Work In Progress",
            "Code Review",
            "qa",
        ]:
            issue = {
                "changelog": {
                    "histories": [
                        {
                            "created": "2026-01-20T09:00:00+00:00",
                            "items": [{"field": "status", "toString": status_name}],
                        }
                    ]
                }
            }
            result = _find_first_in_progress(issue)
            assert result is not None, f"Should recognize '{status_name}'"

    def test_returns_none_when_no_in_progress(self) -> None:
        """Should return None if no In Progress transition found."""
        issue = {
            "changelog": {
                "histories": [
                    {
                        "created": "2026-01-20T09:00:00+00:00",
                        "items": [{"field": "status", "toString": "Done"}],
                    }
                ]
            }
        }

        result = _find_first_in_progress(issue)

        assert result is None

    def test_returns_none_when_no_changelog(self) -> None:
        """Should return None if no changelog."""
        issue = {}
        assert _find_first_in_progress(issue) is None

        issue = {"changelog": {}}
        assert _find_first_in_progress(issue) is None

        issue = {"changelog": {"histories": []}}
        assert _find_first_in_progress(issue) is None


class TestBusinessDaysDiff:
    """Test business days calculation."""

    def test_same_day(self) -> None:
        """Should calculate fraction of a day."""
        start = datetime(2026, 1, 20, 9, 0, 0)  # Monday 9am
        end = datetime(2026, 1, 20, 18, 0, 0)  # Monday 6pm
        assert business_days_diff(start, end) == pytest.approx(1.0)

    def test_two_business_days(self) -> None:
        """Should calculate two full business days."""
        start = datetime(2026, 1, 20, 9, 0, 0)  # Monday 9am
        end = datetime(2026, 1, 21, 18, 0, 0)  # Tuesday 6pm
        assert business_days_diff(start, end) == pytest.approx(2.0)

    def test_skip_weekend(self) -> None:
        """Should skip weekend days."""
        start = datetime(2026, 1, 17, 9, 0, 0)  # Friday 9am
        end = datetime(2026, 1, 19, 18, 0, 0)  # Sunday 6pm
        # Only Friday counts = 1 day
        assert business_days_diff(start, end) == pytest.approx(1.0)

    def test_week_with_weekend(self) -> None:
        """Should calculate business days across weekend."""
        start = datetime(2026, 1, 17, 9, 0, 0)  # Friday 9am
        end = datetime(2026, 1, 20, 18, 0, 0)  # Monday 6pm
        # Friday + Monday = 2 days
        assert business_days_diff(start, end) == pytest.approx(2.0)

    def test_end_before_start(self) -> None:
        """Should return 0 if end is before start."""
        start = datetime(2026, 1, 20, 18, 0, 0)
        end = datetime(2026, 1, 20, 9, 0, 0)
        assert business_days_diff(start, end) == pytest.approx(0.0)
