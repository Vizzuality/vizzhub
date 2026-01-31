"""
pr_size - Pull Request size metrics

== SPEC ==

Formula:
    pr_size_median = median(pr.additions + pr.deletions) for merged PRs

Definition:
    Measures the typical size of pull requests by calculating the median
    total lines changed (additions + deletions) across merged PRs.

    Only counts PRs merged to target branches (dev, develop, main, master).

Data Source:
    GitHub API:
    - GET /repos/{owner}/{repo}/pulls?state=closed (list merged PRs)
    - GET /repos/{owner}/{repo}/pulls/{number} (get PR details with size)

Target:
    PR_size_t from config (default: 400 lines)

Normalization:
    Lower is better → min(1, 400 / value)

Edge Cases:
    - No merged PRs: return None (neutral 0.5)
    - Single PR: that PR's size
    - PRs without size data: skip

Industry Benchmarks:
    - Elite: <200 lines
    - High: 200-400 lines
    - Medium: 400-800 lines
    - Low: >800 lines

== END SPEC ==
"""

import asyncio
import logging
import statistics
from datetime import date
from typing import TYPE_CHECKING

from app.services.collectors.github.utils import (
    MAX_CONCURRENT_REQUESTS,
    filter_target_branch_prs,
    get_merged_prs,
)

if TYPE_CHECKING:
    from app.services.collectors.github.client import GitHubClient

logger = logging.getLogger(__name__)


async def collect_pr_size(
    client: "GitHubClient",
    repo_slug: str,
    period_start: date | None = None,
    period_end: date | None = None,
) -> dict:
    """
    Collect PR size metrics from GitHub.

    Args:
        client: Authenticated GitHubClient instance
        repo_slug: Repository in "owner/repo" format
        period_start: Optional start date for punctual filtering (inclusive)
        period_end: Optional end date to filter PRs merged by this date

    Returns:
        dict with pr_size_median
    """
    owner, repo = client.validate_repo_slug(repo_slug)

    merged_prs = await get_merged_prs(client, owner, repo, period_start=period_start, period_end=period_end)

    if not merged_prs:
        return {"pr_size_median": None}

    target_prs = filter_target_branch_prs(merged_prs)

    if not target_prs:
        return {"pr_size_median": None}

    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

    async def get_pr_size_with_semaphore(pr: dict) -> int | None:
        async with semaphore:
            return await _get_pr_size(client, owner, repo, pr["number"])

    size_results = await asyncio.gather(
        *[get_pr_size_with_semaphore(pr) for pr in target_prs]
    )

    sizes = [s for s in size_results if s is not None]

    if not sizes:
        return {"pr_size_median": None}

    median_size = statistics.median(sizes)
    return {"pr_size_median": round(median_size, 1)}


async def _get_pr_size(
    client: "GitHubClient", owner: str, repo: str, pr_number: int
) -> int | None:
    """
    Get the total size (additions + deletions) for a PR.

    Returns None if unable to fetch.
    """
    http_client = await client.get_client()

    try:
        response = await http_client.get(
            f"/repos/{owner}/{repo}/pulls/{pr_number}",
        )

        if response.status_code == 200:
            pr_data = response.json()
            additions = pr_data.get("additions")
            deletions = pr_data.get("deletions")
            if additions is not None and deletions is not None:
                return additions + deletions

    except Exception as e:
        logger.warning("Failed to get size for PR #%d in %s/%s: %s", pr_number, owner, repo, e)

    return None
