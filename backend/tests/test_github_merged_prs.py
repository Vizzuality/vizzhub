"""Tests for merged-PR pagination in the GitHub collectors."""

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.modules.scorecard.services.collectors.github.utils import get_merged_prs

PER_PAGE = 100


def _pr(number: int, updated: str, merged: str | None) -> dict:
    return {
        "number": number,
        "updated_at": updated,
        "merged_at": merged,
        "base": {"ref": "main"},
    }


def _page(prs: list[dict]) -> MagicMock:
    return MagicMock(status_code=200, json=lambda: prs)


def _full_page(start: int, updated: str, merged: str) -> list[dict]:
    return [_pr(start + i, updated, merged) for i in range(PER_PAGE)]


@pytest.mark.asyncio
async def test_stops_paging_once_prs_predate_the_period(mock_github_client) -> None:
    """A long repo history must not be paged through when the period is recent."""
    recent = _full_page(1, "2026-11-10T10:00:00Z", "2026-11-10T09:00:00Z")
    mixed = [
        _pr(500, "2026-11-03T10:00:00Z", "2026-11-03T09:00:00Z"),
        _pr(501, "2026-10-20T10:00:00Z", "2026-10-20T09:00:00Z"),
        *_full_page(502, "2026-10-01T10:00:00Z", "2026-10-01T09:00:00Z")[:-1],
    ]
    old = _full_page(1000, "2025-01-01T10:00:00Z", "2025-01-01T09:00:00Z")
    mock_http = AsyncMock()
    mock_http.get = AsyncMock(side_effect=[_page(recent), _page(mixed), _page(old)])
    mock_github_client.get_client = AsyncMock(return_value=mock_http)

    prs = await get_merged_prs(
        mock_github_client,
        "owner",
        "repo",
        max_results=500,
        period_start=date(2026, 11, 1),
        period_end=date(2026, 11, 30),
    )

    assert mock_http.get.await_count == 2
    assert len(prs) == PER_PAGE + 1
    assert prs[-1]["number"] == 500


@pytest.mark.asyncio
async def test_pr_updated_on_period_start_is_kept(
    mock_github_client,
) -> None:
    """A PR updated on the first day of the period is still inside it."""
    page = [_pr(1, "2026-11-01T00:30:00Z", "2026-11-01T00:10:00Z")]
    mock_http = AsyncMock()
    mock_http.get = AsyncMock(return_value=_page(page))
    mock_github_client.get_client = AsyncMock(return_value=mock_http)

    prs = await get_merged_prs(mock_github_client, "owner", "repo", period_start=date(2026, 11, 1))

    assert [pr["number"] for pr in prs] == [1]


@pytest.mark.asyncio
async def test_without_period_start_pages_until_the_end(mock_github_client) -> None:
    """With no period start every page is read (cumulative from the beginning)."""
    first = _full_page(1, "2026-11-10T10:00:00Z", "2026-11-10T09:00:00Z")
    last = [_pr(200, "2020-01-01T10:00:00Z", "2020-01-01T09:00:00Z")]
    mock_http = AsyncMock()
    mock_http.get = AsyncMock(side_effect=[_page(first), _page(last)])
    mock_github_client.get_client = AsyncMock(return_value=mock_http)

    prs = await get_merged_prs(mock_github_client, "owner", "repo", max_results=500)

    assert mock_http.get.await_count == 2
    assert len(prs) == PER_PAGE + 1
