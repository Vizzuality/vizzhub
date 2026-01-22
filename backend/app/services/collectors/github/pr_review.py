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
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.collectors.github.client import GitHubClient


TARGET_BRANCHES = {"dev", "develop", "main", "master", "development"}
MAX_CONCURRENT_REQUESTS = 20


async def collect_pr_review(client: "GitHubClient", repo_slug: str) -> dict:
    """
    Collect PR review metrics from GitHub.

    Args:
        client: Authenticated GitHubClient instance
        repo_slug: Repository in "owner/repo" format

    Returns:
        dict with prs_without_review, total_merged_prs, pr_review_ratio
    """
    owner, repo = client.validate_repo_slug(repo_slug)

    merged_prs = await _get_merged_prs(client, owner, repo)

    if not merged_prs:
        return {
            "prs_without_review": 0,
            "total_merged_prs": 0,
            "pr_review_ratio": None,
        }

    target_prs = [
        pr
        for pr in merged_prs
        if (pr.get("base", {}).get("ref") or "").lower() in TARGET_BRANCHES
    ]

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


async def _get_merged_prs(
    client: "GitHubClient", owner: str, repo: str, max_results: int = 500
) -> list[dict]:
    """Get merged PRs from repository."""
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

    except Exception:
        pass

    return False
