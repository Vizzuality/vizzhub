"""Tests for post-contract tasks collector."""

from datetime import date, timedelta
from unittest.mock import AsyncMock

import pytest

from app.modules.scorecard.services.collectors.jira.post_contract_tasks import (
    GRACE_PERIOD_DAYS,
    collect_post_contract_tasks,
)


@pytest.fixture
def mock_jira_client():
    """Create a mock JiraClient."""
    client = AsyncMock()
    return client


class TestCollectPostContractTasks:
    """Test collect_post_contract_tasks function."""

    @pytest.mark.asyncio
    async def test_returns_none_when_no_end_date(self, mock_jira_client) -> None:
        """Should return None when project has no end_date."""
        result = await collect_post_contract_tasks(
            mock_jira_client, "PROJ", end_date=None
        )

        assert result["post_contract_tasks"] is None
        assert result["post_contract_cutoff"] is None
        mock_jira_client.count_issues.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_none_when_cutoff_in_future(self, mock_jira_client) -> None:
        """Should return None when cutoff date is still in the future."""
        future_end = date.today() - timedelta(days=10)  # Only 10 days ago

        result = await collect_post_contract_tasks(
            mock_jira_client, "PROJ", end_date=future_end
        )

        assert result["post_contract_tasks"] is None
        assert result["post_contract_cutoff"] is not None
        mock_jira_client.count_issues.assert_not_called()

    @pytest.mark.asyncio
    async def test_returns_count_when_cutoff_passed(self, mock_jira_client) -> None:
        """Should return task count when cutoff date has passed."""
        old_end = date.today() - timedelta(days=GRACE_PERIOD_DAYS + 10)
        mock_jira_client.count_issues = AsyncMock(return_value=5)

        result = await collect_post_contract_tasks(
            mock_jira_client, "PROJ", end_date=old_end
        )

        assert result["post_contract_tasks"] == 5
        assert result["post_contract_cutoff"] is not None
        mock_jira_client.count_issues.assert_called_once()

    @pytest.mark.asyncio
    async def test_returns_zero_when_no_tasks_found(self, mock_jira_client) -> None:
        """Should return 0 when no tasks created after cutoff."""
        old_end = date.today() - timedelta(days=GRACE_PERIOD_DAYS + 10)
        mock_jira_client.count_issues = AsyncMock(return_value=0)

        result = await collect_post_contract_tasks(
            mock_jira_client, "PROJ", end_date=old_end
        )

        assert result["post_contract_tasks"] == 0

    @pytest.mark.asyncio
    async def test_jql_includes_correct_date(self, mock_jira_client) -> None:
        """Should query for tasks created after end_date + grace period."""
        end_date = date(2025, 1, 1)
        expected_cutoff = date(2025, 1, 31)  # 30 days later
        mock_jira_client.count_issues = AsyncMock(return_value=0)

        await collect_post_contract_tasks(mock_jira_client, "PROJ", end_date=end_date)

        call_args = mock_jira_client.count_issues.call_args
        jql = call_args[0][1]
        assert "2025-01-31" in jql
        assert "type IN (Story, Task, Bug)" in jql
        assert "created >=" in jql

    @pytest.mark.asyncio
    async def test_grace_period_is_30_days(self) -> None:
        """Grace period should be 30 days."""
        assert GRACE_PERIOD_DAYS == 30


class TestEdgeCases:
    """Test edge cases for post-contract tasks."""

    @pytest.mark.asyncio
    async def test_exactly_30_days_ago_queries_jira(self, mock_jira_client) -> None:
        """End date exactly 30 days ago means cutoff is today - should query Jira."""
        end_date = date.today() - timedelta(days=GRACE_PERIOD_DAYS)
        mock_jira_client.count_issues = AsyncMock(return_value=1)

        result = await collect_post_contract_tasks(
            mock_jira_client, "PROJ", end_date=end_date
        )

        # Cutoff is today, so we query for tasks created today
        assert result["post_contract_tasks"] == 1
        mock_jira_client.count_issues.assert_called_once()

    @pytest.mark.asyncio
    async def test_31_days_ago_returns_count(self, mock_jira_client) -> None:
        """End date 31 days ago means cutoff was yesterday - should return count."""
        end_date = date.today() - timedelta(days=GRACE_PERIOD_DAYS + 1)
        mock_jira_client.count_issues = AsyncMock(return_value=2)

        result = await collect_post_contract_tasks(
            mock_jira_client, "PROJ", end_date=end_date
        )

        assert result["post_contract_tasks"] == 2
