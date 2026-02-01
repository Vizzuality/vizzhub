"""Tests for defect_density indicator.

Tests cover:
- Collection from Jira API
- Calculation formula
- Edge cases (zero tasks, zero bugs)
"""

from unittest.mock import AsyncMock

import pytest

from app.services.collectors.jira.defect_density import (
    calculate_defect_density,
    collect_defect_density,
)


class TestCollectDefectDensity:
    """Test collect_defect_density function."""

    @pytest.mark.asyncio
    async def test_collect_defect_density_calls_correct_jql(self) -> None:
        """Should count all bugs and completed tasks."""
        mock_client = AsyncMock()
        mock_client.count_issues = AsyncMock(return_value=0)

        await collect_defect_density(mock_client, "PROJ")

        calls = mock_client.count_issues.call_args_list
        assert len(calls) == 2

        # First call: all bugs (not filtered by status)
        assert calls[0][0][0] == "PROJ"
        assert calls[0][0][1] == "type = Bug"

        # Second call: completed tasks
        assert calls[1][0][0] == "PROJ"
        assert "type in (Story, Task, Sub-task)" in calls[1][0][1]
        assert "statusCategory = Done" in calls[1][0][1]

    @pytest.mark.asyncio
    async def test_collect_defect_density_returns_counts(self) -> None:
        """Should return bugs_total and tasks_completed counts."""
        mock_client = AsyncMock()

        async def mock_count(project, jql):
            if "type = Bug" in jql:
                return 15
            if "Story, Task, Sub-task" in jql:
                return 200
            return 0

        mock_client.count_issues = AsyncMock(side_effect=mock_count)

        result = await collect_defect_density(mock_client, "TEST")

        assert result["bugs_total"] == 15
        assert result["tasks_completed"] == 200


class TestCalculateDefectDensity:
    """Test calculate_defect_density function."""

    def test_calculate_defect_density_basic(self) -> None:
        """Should calculate defects per 100 tasks."""
        result = calculate_defect_density(bugs_total=6, tasks_completed=200)
        assert result == pytest.approx(3.0)

    def test_calculate_defect_density_zero_bugs(self) -> None:
        """Zero bugs should return 0."""
        result = calculate_defect_density(bugs_total=0, tasks_completed=100)
        assert result == pytest.approx(0.0)

    def test_calculate_defect_density_zero_tasks(self) -> None:
        """Zero tasks should return 0 (no work, no defects possible)."""
        result = calculate_defect_density(bugs_total=5, tasks_completed=0)
        assert result == pytest.approx(0.0)

    def test_calculate_defect_density_high_ratio(self) -> None:
        """Should handle high defect ratios."""
        result = calculate_defect_density(bugs_total=50, tasks_completed=100)
        assert result == pytest.approx(50.0)

    def test_calculate_defect_density_fractional(self) -> None:
        """Should handle fractional results."""
        result = calculate_defect_density(bugs_total=1, tasks_completed=300)
        assert abs(result - 0.333) < 0.01

    def test_calculate_defect_density_single_task(self) -> None:
        """Should handle single task."""
        result = calculate_defect_density(bugs_total=1, tasks_completed=1)
        assert result == pytest.approx(100.0)
