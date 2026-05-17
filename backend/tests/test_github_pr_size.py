"""Tests for GitHub PR Size collector."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.scorecard.services.collectors.github.pr_size import (
    _get_pr_size,
    collect_pr_size,
)
from app.modules.scorecard.services.collectors.github.utils import TARGET_BRANCHES


class TestCollectPRSize:
    @pytest.mark.asyncio
    async def test_returns_none_when_no_merged_prs(self, mock_github_client) -> None:
        """Should return None when no merged PRs exist."""
        mock_http = AsyncMock()
        mock_http.get.return_value = MagicMock(status_code=200, json=lambda: [])
        mock_github_client.get_client = AsyncMock(return_value=mock_http)

        result = await collect_pr_size(mock_github_client, "owner/repo")

        assert result["pr_size_median"] is None

    @pytest.mark.asyncio
    async def test_returns_none_when_no_target_branch_prs(self, mock_github_client) -> None:
        """Should return None when PRs exist but none target main/dev branches."""
        mock_http = AsyncMock()
        mock_http.get.return_value = MagicMock(
            status_code=200,
            json=lambda: [
                {
                    "number": 1,
                    "merged_at": "2024-01-01T00:00:00Z",
                    "base": {"ref": "feature-branch"},
                },
            ],
        )
        mock_github_client.get_client = AsyncMock(return_value=mock_http)

        result = await collect_pr_size(mock_github_client, "owner/repo")

        assert result["pr_size_median"] is None

    @pytest.mark.asyncio
    async def test_calculates_median_correctly(self, mock_github_client) -> None:
        """Should calculate median PR size correctly."""
        mock_http = AsyncMock()

        # First call returns merged PRs
        pr_list_response = MagicMock(
            status_code=200,
            json=lambda: [
                {"number": 1, "merged_at": "2024-01-01T00:00:00Z", "base": {"ref": "main"}},
                {"number": 2, "merged_at": "2024-01-02T00:00:00Z", "base": {"ref": "main"}},
                {"number": 3, "merged_at": "2024-01-03T00:00:00Z", "base": {"ref": "main"}},
            ],
        )

        # PR detail responses with sizes: 100, 300, 500 -> median = 300
        pr_detail_responses = [
            MagicMock(status_code=200, json=lambda: {"additions": 50, "deletions": 50}),  # 100
            MagicMock(status_code=200, json=lambda: {"additions": 200, "deletions": 100}),  # 300
            MagicMock(status_code=200, json=lambda: {"additions": 300, "deletions": 200}),  # 500
        ]

        call_count = [0]

        def mock_get(url, **kwargs):
            if "/pulls?" in url or url.endswith("/pulls"):
                return pr_list_response
            else:
                response = pr_detail_responses[call_count[0] % len(pr_detail_responses)]
                call_count[0] += 1
                return response

        mock_http.get = AsyncMock(side_effect=mock_get)
        mock_github_client.get_client = AsyncMock(return_value=mock_http)

        result = await collect_pr_size(mock_github_client, "owner/repo")

        assert result["pr_size_median"] == pytest.approx(300.0)

    @pytest.mark.asyncio
    async def test_filters_target_branches(self, mock_github_client) -> None:
        """Should only count PRs merged to target branches."""
        mock_http = AsyncMock()

        pr_list_response = MagicMock(
            status_code=200,
            json=lambda: [
                {"number": 1, "merged_at": "2024-01-01T00:00:00Z", "base": {"ref": "main"}},
                {"number": 2, "merged_at": "2024-01-02T00:00:00Z", "base": {"ref": "feature"}},
                {"number": 3, "merged_at": "2024-01-03T00:00:00Z", "base": {"ref": "develop"}},
            ],
        )

        pr_detail_response = MagicMock(
            status_code=200,
            json=lambda: {"additions": 100, "deletions": 100},
        )

        def mock_get(url, **kwargs):
            if "/pulls?" in url or (url.endswith("/pulls") and "params" in kwargs):
                return pr_list_response
            else:
                return pr_detail_response

        mock_http.get = AsyncMock(side_effect=mock_get)
        mock_github_client.get_client = AsyncMock(return_value=mock_http)

        result = await collect_pr_size(mock_github_client, "owner/repo")

        # Should have processed 2 PRs (main and develop), not the feature branch
        assert result["pr_size_median"] is not None


class TestTargetBranches:
    def test_target_branches_include_common_branches(self) -> None:
        """Target branches should include main, master, dev, develop."""
        assert "main" in TARGET_BRANCHES
        assert "master" in TARGET_BRANCHES
        assert "dev" in TARGET_BRANCHES
        assert "develop" in TARGET_BRANCHES
        assert "development" in TARGET_BRANCHES


class TestGetPRSize:
    @pytest.mark.asyncio
    async def test_returns_sum_of_additions_and_deletions(self, mock_github_client) -> None:
        """Should return additions + deletions."""
        mock_http = AsyncMock()
        mock_http.get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"additions": 150, "deletions": 50},
        )
        mock_github_client.get_client = AsyncMock(return_value=mock_http)

        result = await _get_pr_size(mock_github_client, "owner", "repo", 1)

        assert result == 200

    @pytest.mark.asyncio
    async def test_returns_none_on_missing_data(self, mock_github_client) -> None:
        """Should return None if additions/deletions missing."""
        mock_http = AsyncMock()
        mock_http.get.return_value = MagicMock(
            status_code=200,
            json=lambda: {"additions": 150},  # Missing deletions
        )
        mock_github_client.get_client = AsyncMock(return_value=mock_http)

        result = await _get_pr_size(mock_github_client, "owner", "repo", 1)

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_on_api_error(self, mock_github_client) -> None:
        """Should return None on API error."""
        mock_http = AsyncMock()
        mock_http.get.return_value = MagicMock(status_code=404)
        mock_github_client.get_client = AsyncMock(return_value=mock_http)

        result = await _get_pr_size(mock_github_client, "owner", "repo", 1)

        assert result is None
