"""
pr_review - Pull Request review metrics

== SPEC ==

Formula:
    pr_review_ratio = prs_with_review / total_merged_prs
    prs_without_review = total_merged_prs - prs_with_review

Definition:
    Measures code review coverage by counting merged PRs that had
    at least one review vs those merged without any review.

    Only counts PRs merged to target branches (dev, develop, main, master).

Data Source:
    GitHub API:
    - GET /repos/{owner}/{repo}/pulls?state=closed (list merged PRs)
    - GET /repos/{owner}/{repo}/pulls/{pr_number}/reviews (check reviews)

Target:
    PR_noReview_t from config DB (default: 0.02 = max 2% without review)

Normalization:
    Lower is better for prs_without_review ratio

Edge Cases:
    - No merged PRs: ratio = None (neutral)
    - API error: return None values

== END SPEC ==
"""

import asyncio
import logging
from datetime import date
from typing import TYPE_CHECKING

from app.modules.scorecard.services.collectors.github.utils import (
    MAX_CONCURRENT_REQUESTS,
    filter_target_branch_prs,
    get_merged_prs,
)

if TYPE_CHECKING:
    from app.modules.scorecard.services.collectors.github.client import GitHubClient

logger = logging.getLogger(__name__)


async def collect_pr_review(
    client: "GitHubClient",
    repo_slug: str,
    period_start: date | None = None,
    period_end: date | None = None,
) -> dict:
    """
    Collect PR review metrics from GitHub.

    Args:
        client: Authenticated GitHubClient instance
        repo_slug: Repository in "owner/repo" format
        period_start: Optional start date for punctual filtering (inclusive)
        period_end: Optional end date to filter PRs merged by this date

    Returns:
        dict with prs_without_review, total_merged_prs, pr_review_ratio
    """
    owner, repo = client.validate_repo_slug(repo_slug)

    merged_prs = await get_merged_prs(
        client, owner, repo, max_results=500, period_start=period_start, period_end=period_end
    )

    if not merged_prs:
        return {
            "prs_without_review": 0,
            "total_merged_prs": 0,
            "pr_review_ratio": None,
        }

    target_prs = filter_target_branch_prs(merged_prs)

    if not target_prs:
        return {
            "prs_without_review": 0,
            "total_merged_prs": 0,
            "pr_review_ratio": None,
        }

    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

    async def check_review_with_semaphore(pr_number: int) -> bool:
        async with semaphore:
            return await _pr_has_review(client, owner, repo, pr_number)

    review_results = await asyncio.gather(
        *[check_review_with_semaphore(pr["number"]) for pr in target_prs]
    )

    total = len(target_prs)
    with_review = sum(1 for has_review in review_results if has_review)
    without_review = total - with_review
    ratio = (with_review / total) if total > 0 else None

    return {
        "prs_without_review": without_review,
        "total_merged_prs": total,
        "pr_review_ratio": ratio,
    }


async def _pr_has_review(
    client: "GitHubClient", owner: str, repo: str, pr_number: int
) -> bool:
    """Check if a PR has at least one review."""
    http_client = await client.get_client()

    try:
        response = await http_client.get(
            f"/repos/{owner}/{repo}/pulls/{pr_number}/reviews",
            params={"per_page": 1},
        )

        if response.status_code == 200:
            reviews = response.json()
            return len(reviews) > 0

    except Exception as e:
        logger.warning("Failed to check review for PR #%d in %s/%s: %s", pr_number, owner, repo, e)

    return False
