"""
Shared utilities for GitHub collectors.

This module contains common functions and constants used across multiple
GitHub collector modules to avoid duplication.
"""

import logging
from datetime import date, datetime, timezone
from typing import TYPE_CHECKING

from app.services.collectors.utils import parse_iso_datetime

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from app.services.collectors.github.client import GitHubClient

# Re-export for backwards compatibility
parse_github_datetime = parse_iso_datetime

TARGET_BRANCHES = frozenset({"dev", "develop", "main", "master", "development"})
MAX_CONCURRENT_REQUESTS = 20


def _is_within_period(
    item_date: datetime | None,
    period_start: date | None,
    period_end: date | None,
) -> bool:
    """Check if a datetime falls within the specified period."""
    if not item_date:
        return True
    if period_start and item_date.date() < period_start:
        return False
    if period_end and item_date.date() > period_end:
        return False
    return True


def _extract_merged_date(pr: dict) -> datetime | None:
    """Extract and parse merged_at date from PR."""
    merged_at = pr.get("merged_at")
    if not merged_at:
        return None
    return parse_iso_datetime(merged_at)


def _extract_release_date(release: dict) -> datetime | None:
    """Extract and parse published/created date from release."""
    date_str = release.get("published_at") or release.get("created_at")
    if not date_str:
        return None
    return parse_iso_datetime(date_str)


async def get_merged_prs(
    client: "GitHubClient",
    owner: str,
    repo: str,
    max_results: int = 100,
    period_start: date | None = None,
    period_end: date | None = None,
) -> list[dict]:
    """
    Get merged PRs from repository.

    Args:
        client: Authenticated GitHubClient instance
        owner: Repository owner
        repo: Repository name
        max_results: Maximum number of PRs to fetch
        period_start: Optional start date for punctual filtering (inclusive)
        period_end: Optional end date to filter PRs merged by this date

    Returns:
        List of merged PR dicts
    """
    http_client = await client.get_client()
    merged_prs: list[dict] = []
    page = 1
    per_page = 100

    while len(merged_prs) < max_results:
        try:
            response = await http_client.get(
                f"/repos/{owner}/{repo}/pulls",
                params={
                    "state": "closed",
                    "per_page": per_page,
                    "page": page,
                    "sort": "updated",
                    "direction": "desc",
                },
            )

            if response.status_code != 200:
                break

            prs = response.json()
            if not prs:
                break

            for pr in prs:
                merged_date = _extract_merged_date(pr)
                if not merged_date:
                    continue
                if not _is_within_period(merged_date, period_start, period_end):
                    continue
                merged_prs.append(pr)
                if len(merged_prs) >= max_results:
                    break

            if len(prs) < per_page:
                break

            page += 1

        except Exception as e:
            logger.warning("Failed to fetch PRs for %s/%s page %d: %s", owner, repo, page, e)
            break

    return merged_prs


def filter_target_branch_prs(prs: list[dict]) -> list[dict]:
    """
    Filter PRs to only those merged to target branches.

    Args:
        prs: List of PR dicts

    Returns:
        Filtered list of PRs targeting main/dev branches
    """
    return [
        pr
        for pr in prs
        if (pr.get("base", {}).get("ref") or "").lower() in TARGET_BRANCHES
    ]


async def get_releases(
    client: "GitHubClient",
    owner: str,
    repo: str,
    include_prereleases: bool = True,
    include_drafts: bool = False,
    max_results: int = 200,
    period_start: date | None = None,
    period_end: date | None = None,
) -> list[dict]:
    """
    Get releases from repository with filtering options.

    Args:
        client: Authenticated GitHubClient instance
        owner: Repository owner
        repo: Repository name
        include_prereleases: Whether to include prerelease versions
        include_drafts: Whether to include draft releases
        max_results: Maximum number of releases to fetch
        period_start: Optional start date for punctual filtering (inclusive)
        period_end: Optional end date to filter releases published by this date

    Returns:
        List of release dicts
    """
    http_client = await client.get_client()
    releases: list[dict] = []
    page = 1
    per_page = 100

    while len(releases) < max_results:
        try:
            response = await http_client.get(
                f"/repos/{owner}/{repo}/releases",
                params={
                    "per_page": per_page,
                    "page": page,
                },
            )

            if response.status_code != 200:
                break

            page_releases = response.json()
            if not page_releases:
                break

            for release in page_releases:
                if not include_drafts and release.get("draft"):
                    continue
                if not include_prereleases and release.get("prerelease"):
                    continue
                release_date = _extract_release_date(release)
                if not _is_within_period(release_date, period_start, period_end):
                    continue
                releases.append(release)
                if len(releases) >= max_results:
                    break

            if len(page_releases) < per_page:
                break

            page += 1

        except Exception as e:
            logger.warning("Failed to fetch releases for %s/%s page %d: %s", owner, repo, page, e)
            break

    return releases


def parse_release_date(release: dict) -> datetime:
    """
    Parse the release published date.

    Falls back to created_at if published_at is not available.

    Args:
        release: Release dict from GitHub API

    Returns:
        datetime object (timezone-aware)
    """
    published_at = release.get("published_at")
    if published_at:
        return datetime.fromisoformat(published_at.replace("Z", "+00:00"))
    created_at = release.get("created_at")
    if created_at:
        return datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    return datetime.min.replace(tzinfo=timezone.utc)


