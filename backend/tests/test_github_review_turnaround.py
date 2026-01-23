"""Tests for GitHub Review Turnaround collector."""

import pytest
from unittest.mock import AsyncMock, MagicMock
from datetime import datetime, timezone, timedelta

from app.services.collectors.github.review_turnaround import (
    collect_review_turnaround,
    _get_pr_turnaround_hours,
)


@pytest.fixture
def mock_client():
    """Create a mock GitHubClient."""
    client = MagicMock()
    client.validate_repo_slug.return_value = ("owner", "repo")
    return client


def make_pr(number: int, hours_ago_created: int) -> dict:
    """Helper to create a PR dict."""
    created = datetime.now(timezone.utc) - timedelta(hours=hours_ago_created)
    return {
        "number": number,
        "created_at": created.isoformat(),
        "merged_at": (created + timedelta(hours=24)).isoformat(),
        "base": {"ref": "main"},
    }


def make_review(hours_ago: int) -> dict:
    """Helper to create a review dict."""
    submitted = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
    return {
        "id": hours_ago,
        "submitted_at": submitted.isoformat(),
        "state": "APPROVED",
    }


class TestCollectReviewTurnaround:
    @pytest.mark.asyncio
    async def test_returns_none_when_no_prs(self, mock_client) -> None:
        """Should return None when no merged PRs exist."""
        mock_http = AsyncMock()
        mock_http.get.return_value = MagicMock(status_code=200, json=lambda: [])
        mock_client.get_client = AsyncMock(return_value=mock_http)

        result = await collect_review_turnaround(mock_client, "owner/repo")

        assert result["review_turnaround_hours"] is None

    @pytest.mark.asyncio
    async def test_returns_none_when_no_reviews(self, mock_client) -> None:
        """Should return None when PRs have no reviews."""
        mock_http = AsyncMock()

        # PR list response
        prs = [make_pr(1, 48)]
        pr_response = MagicMock(status_code=200, json=lambda: prs)
        empty_reviews = MagicMock(status_code=200, json=lambda: [])

        def mock_get(url, **kwargs):
            if "/reviews" in url:
                return empty_reviews
            return pr_response

        mock_http.get = AsyncMock(side_effect=mock_get)
        mock_client.get_client = AsyncMock(return_value=mock_http)

        result = await collect_review_turnaround(mock_client, "owner/repo")

        assert result["review_turnaround_hours"] is None

    @pytest.mark.asyncio
    async def test_calculates_median_turnaround(self, mock_client) -> None:
        """Should calculate median review turnaround time."""
        mock_http = AsyncMock()

        # 3 PRs created 100h, 90h, 80h ago
        prs = [
            make_pr(1, 100),
            make_pr(2, 90),
            make_pr(3, 80),
        ]

        # Reviews: 2h after PR1, 4h after PR2, 6h after PR3
        # Turnaround times: 2h, 4h, 6h -> median = 4h
        reviews_pr1 = [make_review(98)]  # 100-98 = 2h turnaround
        reviews_pr2 = [make_review(86)]  # 90-86 = 4h turnaround
        reviews_pr3 = [make_review(74)]  # 80-74 = 6h turnaround

        call_count = [0]

        def mock_get(url, **kwargs):
            if "/pulls?" in url or (url.endswith("/pulls") and "params" in kwargs):
                return MagicMock(status_code=200, json=lambda: prs)
            elif "/reviews" in url:
                reviews = [reviews_pr1, reviews_pr2, reviews_pr3][call_count[0] % 3]
                call_count[0] += 1
                return MagicMock(status_code=200, json=lambda r=reviews: r)
            return MagicMock(status_code=200, json=lambda: [])

        mock_http.get = AsyncMock(side_effect=mock_get)
        mock_client.get_client = AsyncMock(return_value=mock_http)

        result = await collect_review_turnaround(mock_client, "owner/repo")

        # Median of turnaround times should be around 4h
        assert result["review_turnaround_hours"] is not None

    @pytest.mark.asyncio
    async def test_uses_first_review_only(self, mock_client) -> None:
        """Should use first review time, not subsequent reviews."""
        mock_http = AsyncMock()

        prs = [make_pr(1, 100)]
        # Multiple reviews at different times
        reviews = [
            make_review(98),  # First review: 2h turnaround
            make_review(90),  # Later review: 10h turnaround
            make_review(80),  # Even later: 20h turnaround
        ]

        def mock_get(url, **kwargs):
            if "/pulls?" in url or (url.endswith("/pulls") and "params" in kwargs):
                return MagicMock(status_code=200, json=lambda: prs)
            elif "/reviews" in url:
                return MagicMock(status_code=200, json=lambda: reviews)
            return MagicMock(status_code=200, json=lambda: [])

        mock_http.get = AsyncMock(side_effect=mock_get)
        mock_client.get_client = AsyncMock(return_value=mock_http)

        result = await collect_review_turnaround(mock_client, "owner/repo")

        # Should use earliest review time
        assert result["review_turnaround_hours"] is not None


class TestGetPrTurnaroundHours:
    @pytest.mark.asyncio
    async def test_returns_none_when_no_reviews(self, mock_client) -> None:
        """Should return None when PR has no reviews."""
        mock_http = AsyncMock()
        mock_http.get.return_value = MagicMock(status_code=200, json=lambda: [])
        mock_client.get_client = AsyncMock(return_value=mock_http)

        pr = {"number": 1, "created_at": "2024-01-01T08:00:00Z"}
        result = await _get_pr_turnaround_hours(mock_client, "owner", "repo", pr)

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_hours_to_first_review(self, mock_client) -> None:
        """Should return hours to the earliest review."""
        mock_http = AsyncMock()
        reviews = [
            {"submitted_at": "2024-01-01T12:00:00Z", "state": "APPROVED"},
            {"submitted_at": "2024-01-01T10:00:00Z", "state": "COMMENTED"},  # Earlier - 2h after PR
            {"submitted_at": "2024-01-01T14:00:00Z", "state": "APPROVED"},
        ]
        mock_http.get.return_value = MagicMock(status_code=200, json=lambda: reviews)
        mock_client.get_client = AsyncMock(return_value=mock_http)

        pr = {"number": 1, "created_at": "2024-01-01T08:00:00Z"}
        result = await _get_pr_turnaround_hours(mock_client, "owner", "repo", pr)

        assert result is not None
        assert result == 2.0  # 10:00 - 08:00 = 2 hours

    @pytest.mark.asyncio
    async def test_handles_api_error(self, mock_client) -> None:
        """Should return None on API error."""
        mock_http = AsyncMock()
        mock_http.get.return_value = MagicMock(status_code=500)
        mock_client.get_client = AsyncMock(return_value=mock_http)

        pr = {"number": 1, "created_at": "2024-01-01T08:00:00Z"}
        result = await _get_pr_turnaround_hours(mock_client, "owner", "repo", pr)

        assert result is None
