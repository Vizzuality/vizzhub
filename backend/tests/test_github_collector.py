"""Tests for GitHub collector and PR review metrics collection.

This module tests the GitHubCollector which collects metrics from GitHub API,
including PR review coverage for merged pull requests.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from app.core.exceptions import ConfigurationError
from app.services.collectors.github import GitHubCollector
from app.services.collectors.github.client import GitHubClient
from app.services.collectors.github.pr_review import (
    _pr_has_review,
    collect_pr_review,
)
from app.services.collectors.github.utils import TARGET_BRANCHES


class TestGitHubClient:
    """Tests for GitHubClient authentication and validation."""

    @pytest.mark.asyncio
    async def test_github_client_creates_authenticated_client(self) -> None:
        """Client should create httpx client with auth headers."""
        with patch("app.services.collectors.github.client.get_settings") as mock_settings:
            mock_settings.return_value.github_token = "test-token"

            client = GitHubClient()
            http_client = await client._get_client()

            assert str(http_client.base_url) == "https://api.github.com"
            assert http_client.headers["Authorization"] == "Bearer test-token"
            assert http_client.headers["Accept"] == "application/vnd.github+json"
            assert http_client.headers["X-GitHub-Api-Version"] == "2022-11-28"

            await client.close()

    @pytest.mark.asyncio
    async def test_github_client_raises_error_when_no_token(self) -> None:
        """Client should raise ConfigurationError if no token configured."""
        with patch("app.services.collectors.github.client.get_settings") as mock_settings:
            mock_settings.return_value.github_token = ""

            client = GitHubClient()

            with pytest.raises(ConfigurationError, match="GitHub token not configured"):
                await client._get_client()

    def test_validate_repo_slug_valid(self) -> None:
        """Should parse valid owner/repo format."""
        client = GitHubClient()
        owner, repo = client.validate_repo_slug("owner/repo")
        assert owner == "owner"
        assert repo == "repo"

    def test_validate_repo_slug_with_dashes_and_dots(self) -> None:
        """Should accept alphanumeric, dash, dot, underscore characters."""
        client = GitHubClient()
        owner, repo = client.validate_repo_slug("my-org/my.repo_name")
        assert owner == "my-org"
        assert repo == "my.repo_name"

    def test_validate_repo_slug_invalid_format(self) -> None:
        """Should reject invalid formats."""
        client = GitHubClient()

        with pytest.raises(ValueError, match="Invalid repo format"):
            client.validate_repo_slug("invalid")

        with pytest.raises(ValueError, match="Invalid repo format"):
            client.validate_repo_slug("")

        with pytest.raises(ValueError, match="Invalid repo format"):
            client.validate_repo_slug("a/b/c")

    def test_validate_repo_slug_invalid_characters(self) -> None:
        """Should reject special characters in owner/repo."""
        client = GitHubClient()

        with pytest.raises(ValueError, match="Invalid owner format"):
            client.validate_repo_slug("owner@/repo")


class TestPRReviewCollection:
    """Tests for PR review metrics collection."""

    @pytest.mark.asyncio
    async def test_collect_pr_review_no_merged_prs(self) -> None:
        """Should return zeros when no merged PRs exist."""
        mock_client = MagicMock(spec=GitHubClient)
        mock_client.validate_repo_slug.return_value = ("owner", "repo")

        mock_http = AsyncMock()
        mock_http.get.return_value = MagicMock(
            status_code=200,
            json=lambda: [],
        )
        mock_client.get_client = AsyncMock(return_value=mock_http)

        result = await collect_pr_review(mock_client, "owner/repo")

        assert result["prs_without_review"] == 0
        assert result["total_merged_prs"] == 0
        assert result["pr_review_ratio"] is None

    @pytest.mark.asyncio
    async def test_collect_pr_review_with_reviews(self) -> None:
        """Should calculate correct ratio when PRs have reviews."""
        mock_client = MagicMock(spec=GitHubClient)
        mock_client.validate_repo_slug.return_value = ("owner", "repo")

        merged_prs = [
            {"number": 1, "merged_at": "2024-01-01T00:00:00Z", "base": {"ref": "main"}},
            {"number": 2, "merged_at": "2024-01-02T00:00:00Z", "base": {"ref": "main"}},
            {"number": 3, "merged_at": "2024-01-03T00:00:00Z", "base": {"ref": "main"}},
        ]

        mock_http = AsyncMock()

        async def mock_get(url: str, params: dict = None) -> MagicMock:
            if "pulls" in url and "reviews" not in url:
                return MagicMock(status_code=200, json=lambda: merged_prs)
            elif "reviews" in url:
                pr_number = int(url.split("/")[-2])
                if pr_number <= 2:
                    return MagicMock(status_code=200, json=lambda: [{"id": 1}])
                return MagicMock(status_code=200, json=lambda: [])
            return MagicMock(status_code=404)

        mock_http.get = mock_get
        mock_client.get_client = AsyncMock(return_value=mock_http)

        result = await collect_pr_review(mock_client, "owner/repo")

        assert result["total_merged_prs"] == 3
        assert result["prs_without_review"] == 1
        assert result["pr_review_ratio"] == pytest.approx(2 / 3)

    @pytest.mark.asyncio
    async def test_collect_pr_review_ignores_non_target_branches(self) -> None:
        """Should only count PRs merged to target branches."""
        mock_client = MagicMock(spec=GitHubClient)
        mock_client.validate_repo_slug.return_value = ("owner", "repo")

        merged_prs = [
            {"number": 1, "merged_at": "2024-01-01T00:00:00Z", "base": {"ref": "main"}},
            {"number": 2, "merged_at": "2024-01-02T00:00:00Z", "base": {"ref": "feature-branch"}},
        ]

        mock_http = AsyncMock()

        async def mock_get(url: str, params: dict = None) -> MagicMock:
            if "pulls" in url and "reviews" not in url:
                return MagicMock(status_code=200, json=lambda: merged_prs)
            elif "reviews" in url:
                return MagicMock(status_code=200, json=lambda: [{"id": 1}])
            return MagicMock(status_code=404)

        mock_http.get = mock_get
        mock_client.get_client = AsyncMock(return_value=mock_http)

        result = await collect_pr_review(mock_client, "owner/repo")

        assert result["total_merged_prs"] == 1
        assert result["prs_without_review"] == 0
        assert result["pr_review_ratio"] == 1.0


class TestTargetBranches:
    """Tests for target branch configuration."""

    def test_target_branches_contains_common_defaults(self) -> None:
        """Should include common default branch names."""
        assert "main" in TARGET_BRANCHES
        assert "master" in TARGET_BRANCHES
        assert "dev" in TARGET_BRANCHES
        assert "develop" in TARGET_BRANCHES
        assert "development" in TARGET_BRANCHES


class TestGitHubCollector:
    """Tests for the main GitHubCollector class."""

    @pytest.mark.asyncio
    async def test_collector_returns_all_metrics(self) -> None:
        """Collector should return all expected metric fields."""
        with patch("app.services.collectors.github.client.get_settings") as mock_settings:
            mock_settings.return_value.github_token = "test-token"

            collector = GitHubCollector()

            with patch(
                "app.services.collectors.github.collector.collect_pr_review",
                new_callable=AsyncMock,
            ) as mock_collect:
                mock_collect.return_value = {
                    "prs_without_review": 5,
                    "total_merged_prs": 50,
                    "pr_review_ratio": 0.9,
                }

                result = await collector.collect("owner/repo")

            assert result["prs_without_review"] == 5
            assert result["total_merged_prs"] == 50
            assert result["pr_review_ratio"] == 0.9
            assert result["high_severity_vulns"] == 0

            await collector.close()

    @pytest.mark.asyncio
    async def test_collector_validates_repo_slug(self) -> None:
        """Collector should validate repo format before collection."""
        with patch("app.services.collectors.github.client.get_settings") as mock_settings:
            mock_settings.return_value.github_token = "test-token"

            collector = GitHubCollector()

            with pytest.raises(ValueError, match="Invalid repo format"):
                await collector.collect("invalid-format")

            await collector.close()

    @pytest.mark.asyncio
    async def test_test_connection_returns_true_on_success(self) -> None:
        """test_connection should return True when API is reachable."""
        with patch("app.services.collectors.github.client.get_settings") as mock_settings:
            mock_settings.return_value.github_token = "test-token"

            collector = GitHubCollector()

            with patch.object(
                collector._client,
                "_get_client",
                new_callable=AsyncMock,
            ) as mock_get_client:
                mock_http = AsyncMock()
                mock_http.get.return_value = MagicMock(status_code=200)
                mock_get_client.return_value = mock_http

                result = await collector.test_connection()

            assert result is True
            await collector.close()

    @pytest.mark.asyncio
    async def test_test_connection_returns_false_on_failure(self) -> None:
        """test_connection should return False when API is unreachable."""
        with patch("app.services.collectors.github.client.get_settings") as mock_settings:
            mock_settings.return_value.github_token = "test-token"

            collector = GitHubCollector()

            with patch.object(
                collector._client,
                "_get_client",
                new_callable=AsyncMock,
            ) as mock_get_client:
                mock_http = AsyncMock()
                mock_http.get.return_value = MagicMock(status_code=401)
                mock_get_client.return_value = mock_http

                result = await collector.test_connection()

            assert result is False
            await collector.close()
