"""Tests for GitHub Deployment Frequency collector."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone, timedelta

from app.services.collectors.github.deployment_frequency import (
    collect_deployment_frequency,
    LOOKBACK_DAYS,
)
from app.services.collectors.github.utils import get_releases


def make_release(days_ago: int, draft: bool = False, prerelease: bool = False) -> dict:
    """Helper to create a release dict."""
    published = datetime.now(timezone.utc) - timedelta(days=days_ago)
    return {
        "id": days_ago,
        "tag_name": f"v1.0.{days_ago}",
        "published_at": published.isoformat(),
        "draft": draft,
        "prerelease": prerelease,
    }


class TestCollectDeploymentFrequency:
    @pytest.mark.asyncio
    async def test_returns_zero_when_no_releases(self, mock_github_client) -> None:
        """Should return 0 frequency when no releases exist."""
        mock_http = AsyncMock()
        mock_http.get.return_value = MagicMock(status_code=200, json=lambda: [])
        mock_github_client.get_client = AsyncMock(return_value=mock_http)

        result = await collect_deployment_frequency(mock_github_client, "owner/repo")

        assert result["deployment_frequency"] == 0.0
        assert result["release_count_90d"] == 0

    @pytest.mark.asyncio
    async def test_calculates_frequency_correctly(self, mock_github_client) -> None:
        """Should calculate releases per day correctly."""
        mock_http = AsyncMock()
        # 10 releases in 90-day window
        releases = [make_release(i * 9) for i in range(10)]  # Every 9 days
        mock_http.get.return_value = MagicMock(status_code=200, json=lambda: releases)
        mock_github_client.get_client = AsyncMock(return_value=mock_http)

        result = await collect_deployment_frequency(mock_github_client, "owner/repo")

        assert result["release_count_90d"] == 10
        assert result["deployment_frequency"] == pytest.approx(10 / LOOKBACK_DAYS, rel=0.01)

    @pytest.mark.asyncio
    async def test_excludes_draft_releases(self, mock_github_client) -> None:
        """Should exclude draft releases from count."""
        mock_http = AsyncMock()
        releases = [
            make_release(10, draft=False),
            make_release(20, draft=True),  # Should be excluded
            make_release(30, draft=False),
        ]
        mock_http.get.return_value = MagicMock(status_code=200, json=lambda: releases)
        mock_github_client.get_client = AsyncMock(return_value=mock_http)

        result = await collect_deployment_frequency(mock_github_client, "owner/repo")

        assert result["release_count_90d"] == 2  # Only non-draft

    @pytest.mark.asyncio
    async def test_includes_prereleases(self, mock_github_client) -> None:
        """Should include prereleases in count by default."""
        mock_http = AsyncMock()
        releases = [
            make_release(10, prerelease=False),
            make_release(20, prerelease=True),
            make_release(30, prerelease=True),
        ]
        mock_http.get.return_value = MagicMock(status_code=200, json=lambda: releases)
        mock_github_client.get_client = AsyncMock(return_value=mock_http)

        result = await collect_deployment_frequency(mock_github_client, "owner/repo")

        assert result["release_count_90d"] == 3  # All included

    @pytest.mark.asyncio
    async def test_filters_releases_outside_window(self, mock_github_client) -> None:
        """Should only count releases within 90-day window."""
        mock_http = AsyncMock()
        releases = [
            make_release(30),  # Within window
            make_release(60),  # Within window
            make_release(100),  # Outside window
            make_release(120),  # Outside window
        ]
        mock_http.get.return_value = MagicMock(status_code=200, json=lambda: releases)
        mock_github_client.get_client = AsyncMock(return_value=mock_http)

        result = await collect_deployment_frequency(mock_github_client, "owner/repo")

        assert result["release_count_90d"] == 2


class TestGetReleases:
    @pytest.mark.asyncio
    async def test_handles_api_error(self, mock_github_client) -> None:
        """Should return empty list on API error."""
        mock_http = AsyncMock()
        mock_http.get.return_value = MagicMock(status_code=500)
        mock_github_client.get_client = AsyncMock(return_value=mock_http)

        result = await get_releases(mock_github_client, "owner", "repo")

        assert result == []

    @pytest.mark.asyncio
    async def test_handles_pagination(self, mock_github_client) -> None:
        """Should handle paginated results."""
        mock_http = AsyncMock()
        # First page returns 100 releases, second page returns 50
        first_page = [make_release(i) for i in range(100)]
        second_page = [make_release(i + 100) for i in range(50)]

        call_count = [0]

        def mock_get(url, **kwargs):
            page = kwargs.get("params", {}).get("page", 1)
            if page == 1:
                return MagicMock(status_code=200, json=lambda: first_page)
            else:
                return MagicMock(status_code=200, json=lambda: second_page)

        mock_http.get = AsyncMock(side_effect=mock_get)
        mock_github_client.get_client = AsyncMock(return_value=mock_http)

        result = await get_releases(mock_github_client, "owner", "repo")

        # Should have fetched multiple pages
        assert len(result) >= 100
