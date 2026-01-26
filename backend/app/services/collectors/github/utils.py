"""
Shared utilities for GitHub collectors.

This module contains common functions and constants used across multiple
GitHub collector modules to avoid duplication.
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from app.services.collectors.utils import parse_iso_datetime

if TYPE_CHECKING:
    from app.services.collectors.github.client import GitHubClient

# Re-export for backwards compatibility
parse_github_datetime = parse_iso_datetime

TARGET_BRANCHES = frozenset({"dev", "develop", "main", "master", "development"})
MAX_CONCURRENT_REQUESTS = 20


async def get_merged_prs(
    client: "GitHubClient",
    owner: str,
    repo: str,
    max_results: int = 100,
) -> list[dict]:
    """
    Get merged PRs from repository.

    Args:
        client: Authenticated GitHubClient instance
        owner: Repository owner
        repo: Repository name
        max_results: Maximum number of PRs to fetch

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
                if pr.get("merged_at"):
                    merged_prs.append(pr)
                    if len(merged_prs) >= max_results:
                        break

            if len(prs) < per_page:
                break

            page += 1

        except Exception:
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
                releases.append(release)
                if len(releases) >= max_results:
                    break

            if len(page_releases) < per_page:
                break

            page += 1

        except Exception:
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


