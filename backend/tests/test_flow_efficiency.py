"""Tests for flow_efficiency indicator.

Tests cover:
- Collection from Jira API
- Simplified efficiency calculation
- Edge cases (no issues)
"""

from unittest.mock import AsyncMock

import pytest

from app.services.collectors.jira.flow_efficiency import collect_flow_efficiency


class TestCollectFlowEfficiency:
    """Test collect_flow_efficiency function."""

    @pytest.mark.asyncio
    async def test_collect_flow_efficiency_calls_correct_jql(self) -> None:
        """Should query resolved issues from last 90 days."""
        mock_client = AsyncMock()
        mock_client.search_issues = AsyncMock(return_value=[])

        await collect_flow_efficiency(mock_client, "PROJ")

        mock_client.search_issues.assert_called_once()
        call_args = mock_client.search_issues.call_args
        jql = call_args[0][1]

        assert "statusCategory = Done" in jql
        assert "resolutiondate >= -90d" in jql

    @pytest.mark.asyncio
    async def test_collect_flow_efficiency_no_issues(self) -> None:
        """Should return None when no issues found."""
        mock_client = AsyncMock()
        mock_client.search_issues = AsyncMock(return_value=[])

        result = await collect_flow_efficiency(mock_client, "TEST")

        assert result["flow_efficiency"] is None
        assert result["sample_size"] == 0

    @pytest.mark.asyncio
    async def test_collect_flow_efficiency_returns_baseline(self) -> None:
        """Should return 0.5 baseline efficiency (simplified mode)."""
        mock_client = AsyncMock()
        mock_client.search_issues = AsyncMock(return_value=[
            {
                "fields": {
                    "created": "2026-01-20T09:00:00+00:00",
                    "resolutiondate": "2026-01-21T17:00:00+00:00",
                }
            },
            {
                "fields": {
                    "created": "2026-01-19T09:00:00+00:00",
                    "resolutiondate": "2026-01-20T17:00:00+00:00",
                }
            },
        ])

        result = await collect_flow_efficiency(mock_client, "TEST")

        assert result["sample_size"] == 2
        assert result["flow_efficiency"] == 0.5  # Simplified baseline

    @pytest.mark.asyncio
    async def test_collect_flow_efficiency_skips_invalid_issues(self) -> None:
        """Should skip issues with missing dates."""
        mock_client = AsyncMock()
        mock_client.search_issues = AsyncMock(return_value=[
            {"fields": {"created": None, "resolutiondate": "2026-01-20T17:00:00+00:00"}},
            {"fields": {"created": "2026-01-20T09:00:00+00:00", "resolutiondate": None}},
            {
                "fields": {
                    "created": "2026-01-20T09:00:00+00:00",
                    "resolutiondate": "2026-01-20T17:00:00+00:00",
                }
            },
        ])

        result = await collect_flow_efficiency(mock_client, "TEST")

        assert result["sample_size"] == 1
        assert result["flow_efficiency"] == 0.5

    @pytest.mark.asyncio
    async def test_collect_flow_efficiency_all_invalid(self) -> None:
        """Should return None if all issues have invalid dates."""
        mock_client = AsyncMock()
        mock_client.search_issues = AsyncMock(return_value=[
            {"fields": {"created": None, "resolutiondate": None}},
            {"fields": {"created": "2026-01-20T17:00:00+00:00", "resolutiondate": "2026-01-20T09:00:00+00:00"}},
        ])

        result = await collect_flow_efficiency(mock_client, "TEST")

        assert result["flow_efficiency"] is None
        assert result["sample_size"] == 0
