"""Tests for escaped_rate indicator.

Tests cover:
- Collection from Jira API
- Calculation formula
- Edge cases (zero tasks, zero escapes)
"""

from unittest.mock import AsyncMock

import pytest

from app.services.collectors.jira.escaped_rate import (
    calculate_escaped_rate,
    collect_escaped_rate,
)


class TestCollectEscapedRate:
    """Test collect_escaped_rate function."""

    @pytest.mark.asyncio
    async def test_collect_escaped_rate_calls_correct_jql(self) -> None:
        """Should query bugs with Environment in Staging/Production."""
        mock_client = AsyncMock()
        mock_client.count_issues = AsyncMock(return_value=0)

        await collect_escaped_rate(mock_client, "PROJ")

        calls = mock_client.count_issues.call_args_list
        assert len(calls) == 2

        # First call: escaped defects (bugs in Staging/Production)
        assert calls[0][0][0] == "PROJ"
        assert "type = Bug" in calls[0][0][1]
        assert "Environment" in calls[0][0][1]
        assert "Staging" in calls[0][0][1]
        assert "Production" in calls[0][0][1]

        # Second call: resolved tasks
        assert calls[1][0][0] == "PROJ"
        assert "statusCategory = Done" in calls[1][0][1]

    @pytest.mark.asyncio
    async def test_collect_escaped_rate_returns_counts(self) -> None:
        """Should return escaped_defects and tasks_resolved counts."""
        mock_client = AsyncMock()

        async def mock_count(project, jql):
            if "Environment" in jql:
                return 3
            if "statusCategory = Done" in jql:
                return 150
            return 0

        mock_client.count_issues = AsyncMock(side_effect=mock_count)

        result = await collect_escaped_rate(mock_client, "TEST")

        assert result["escaped_defects"] == 3
        assert result["tasks_resolved"] == 150


class TestCalculateEscapedRate:
    """Test calculate_escaped_rate function."""

    def test_calculate_escaped_rate_basic(self) -> None:
        """Should calculate escapes per 100 tasks."""
        result = calculate_escaped_rate(escaped_defects=2, tasks_resolved=200)
        assert result == 1.0

    def test_calculate_escaped_rate_zero_escapes(self) -> None:
        """Zero escapes should return 0 (perfect)."""
        result = calculate_escaped_rate(escaped_defects=0, tasks_resolved=100)
        assert result == 0.0

    def test_calculate_escaped_rate_zero_tasks(self) -> None:
        """Zero tasks should return 0."""
        result = calculate_escaped_rate(escaped_defects=5, tasks_resolved=0)
        assert result == 0.0

    def test_calculate_escaped_rate_high_ratio(self) -> None:
        """Should handle high escape ratios."""
        result = calculate_escaped_rate(escaped_defects=10, tasks_resolved=100)
        assert result == 10.0

    def test_calculate_escaped_rate_fractional(self) -> None:
        """Should handle fractional results."""
        result = calculate_escaped_rate(escaped_defects=1, tasks_resolved=300)
        assert abs(result - 0.333) < 0.01
