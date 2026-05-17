"""Tests for commitment_reliability indicator.

Tests cover:
- Collection from Jira Agile API
- Sprint spillover calculation
- Edge cases (no board, no sprints)
"""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.scorecard.services.collectors.jira.commitment_reliability import (
    collect_commitment_reliability,
)


class TestCollectCommitmentReliability:
    """Test collect_commitment_reliability function."""

    @pytest.mark.asyncio
    async def test_no_scrum_board_returns_none(self) -> None:
        """Should return None if no scrum board found."""
        mock_client = AsyncMock()
        mock_http = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"values": []}
        mock_http.get = AsyncMock(return_value=mock_response)
        mock_http.base_url = "https://api.atlassian.com/ex/jira/cloud-id/rest/api/3"
        mock_client.get_client = AsyncMock(return_value=mock_http)

        result = await collect_commitment_reliability(mock_client, "PROJ")

        assert result["commitment_reliability"] is None
        assert result["committed_issues"] == 0

    @pytest.mark.asyncio
    async def test_no_closed_sprints_returns_none(self) -> None:
        """Should return None if no closed sprints found."""
        mock_client = AsyncMock()
        mock_http = MagicMock()
        mock_http.base_url = "https://api.atlassian.com/ex/jira/cloud-id/rest/api/3"

        # First call returns board, second returns no sprints
        call_count = [0]

        async def mock_get(url, params=None):
            call_count[0] += 1
            response = MagicMock()
            response.status_code = 200
            if call_count[0] == 1:
                response.json.return_value = {"values": [{"id": 1, "name": "Board"}]}
            else:
                response.json.return_value = {"values": [], "isLast": True}
            return response

        mock_http.get = mock_get
        mock_client.get_client = AsyncMock(return_value=mock_http)

        result = await collect_commitment_reliability(mock_client, "PROJ")

        assert result["commitment_reliability"] is None

    @pytest.mark.asyncio
    async def test_calculates_reliability_from_sprints(self) -> None:
        """Should calculate reliability from sprint data."""
        mock_client = AsyncMock()
        mock_http = MagicMock()
        mock_http.base_url = "https://api.atlassian.com/ex/jira/cloud-id/rest/api/3"

        call_count = [0]

        async def mock_get(url, params=None):
            call_count[0] += 1
            response = MagicMock()
            response.status_code = 200
            if "board?" in url or (call_count[0] == 1 and "board" in url):
                response.json.return_value = {"values": [{"id": 1}]}
            elif "sprint" in url:
                response.json.return_value = {
                    "values": [{"id": 101}, {"id": 102}],
                    "isLast": True,
                }
            return response

        mock_http.get = mock_get
        mock_client.get_client = AsyncMock(return_value=mock_http)

        # Mock search_issues for sprint issues
        # Issue A in sprint 101 only (single sprint)
        # Issue B in both sprints (multi sprint)
        # Issue C in sprint 102 only (single sprint)
        async def mock_search(
            project, jql, fields=None, max_results=None, skip_project_prefix=False
        ):
            if "sprint = 101" in jql:
                return [{"key": "PROJ-1"}, {"key": "PROJ-2"}]
            if "sprint = 102" in jql:
                return [{"key": "PROJ-2"}, {"key": "PROJ-3"}]
            return []

        mock_client.search_issues = mock_search

        result = await collect_commitment_reliability(mock_client, "PROJ")

        # 3 committed issues: PROJ-1 (1 sprint), PROJ-2 (2 sprints), PROJ-3 (1 sprint)
        # 2 single sprint, 1 multi sprint
        # Reliability = 2/3 = 0.666...
        assert result["committed_issues"] == 3
        assert result["single_sprint_issues"] == 2
        assert result["multi_sprint_issues"] == 1
        assert abs(result["commitment_reliability"] - 0.666) < 0.01


class TestCommitmentReliabilityEdgeCases:
    """Test edge cases for commitment reliability."""

    @pytest.mark.asyncio
    async def test_api_error_returns_none(self) -> None:
        """Should return None on API error."""
        mock_client = AsyncMock()
        mock_http = MagicMock()
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_http.get = AsyncMock(return_value=mock_response)
        mock_http.base_url = "https://api.atlassian.com/ex/jira/cloud-id/rest/api/3"
        mock_client.get_client = AsyncMock(return_value=mock_http)

        result = await collect_commitment_reliability(mock_client, "PROJ")

        assert result["commitment_reliability"] is None

    @pytest.mark.asyncio
    async def test_all_single_sprint_perfect_score(self) -> None:
        """Should return 1.0 if all issues completed in single sprint."""
        mock_client = AsyncMock()
        mock_http = MagicMock()
        mock_http.base_url = "https://api.atlassian.com/ex/jira/cloud-id/rest/api/3"

        async def mock_get(url, params=None):
            response = MagicMock()
            response.status_code = 200
            if "board?" in url:
                response.json.return_value = {"values": [{"id": 1}]}
            elif "sprint" in url:
                response.json.return_value = {"values": [{"id": 101}], "isLast": True}
            return response

        mock_http.get = mock_get
        mock_client.get_client = AsyncMock(return_value=mock_http)
        mock_client.search_issues = AsyncMock(return_value=[{"key": "PROJ-1"}, {"key": "PROJ-2"}])

        result = await collect_commitment_reliability(mock_client, "PROJ")

        assert result["commitment_reliability"] == pytest.approx(1.0)
        assert result["single_sprint_issues"] == 2
        assert result["multi_sprint_issues"] == 0
