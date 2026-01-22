"""
review_turnaround - Review turnaround time metrics

== SPEC ==

Formula:
    review_turnaround_hours = median(first_review.submitted_at - pr.created_at) in hours

Definition:
    Measures how quickly PRs receive their first review by calculating
    the median time between PR creation and first review submission.

    Only counts PRs merged to target branches (dev, develop, main, master).

Data Source:
    GitHub API:
    - GET /repos/{owner}/{repo}/pulls?state=closed (created_at)
    - GET /repos/{owner}/{repo}/pulls/{pr}/reviews (submitted_at)

Target:
    review_turnaround_t from config (default: 24 hours)

Normalization:
    Lower is better → min(1, 24 / value)

Edge Cases:
    - PR without reviews: skip PR
    - No PRs with reviews: return None (neutral)
    - Review before PR creation: skip (data error)

Industry Benchmarks:
    - Elite: <4 hours
    - High: 4-24 hours
    - Medium: 24-72 hours
    - Low: >72 hours

== END SPEC ==
"""

import asyncio
import statistics
from datetime import datetime
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.collectors.github.client import GitHubClient

TARGET_BRANCHES = {"dev", "develop", "main", "master", "development"}
MAX_CONCURRENT_REQUESTS = 20


async def collect_review_turnaround(client: "GitHubClient", repo_slug: str) -> dict:
    """
    Collect review turnaround time metrics from GitHub.

    Args:
        client: Authenticated GitHubClient instance
        repo_slug: Repository in "owner/repo" format

    Returns:
        dict with review_turnaround_hours
    """
    owner, repo = client.validate_repo_slug(repo_slug)

    merged_prs = await _get_merged_prs(client, owner, repo)

    if not merged_prs:
        return {"review_turnaround_hours": None}

    target_prs = [
        pr
        for pr in merged_prs
        if (pr.get("base", {}).get("ref") or "").lower() in TARGET_BRANCHES
    ]

    if not target_prs:
        return {"review_turnaround_hours": None}

    semaphore = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

    async def get_turnaround_with_semaphore(pr: dict) -> float | None:
        async with semaphore:
            return await _get_pr_turnaround_hours(client, owner, repo, pr)

    turnaround_results = await asyncio.gather(
        *[get_turnaround_with_semaphore(pr) for pr in target_prs]
    )

    valid_turnarounds = [t for t in turnaround_results if t is not None]

    if not valid_turnarounds:
        return {"review_turnaround_hours": None}

    median_hours = statistics.median(valid_turnarounds)
    return {"review_turnaround_hours": round(median_hours, 1)}


async def _get_merged_prs(
    client: "GitHubClient", owner: str, repo: str, max_results: int = 100
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


async def _get_pr_turnaround_hours(
    client: "GitHubClient", owner: str, repo: str, pr: dict
) -> float | None:
    """
    Get the turnaround time in hours for a PR's first review.

    Returns None if no reviews exist or data is invalid.
    """
    http_client = await client.get_client()
    pr_number = pr.get("number")
    pr_created_at = pr.get("created_at")

    if not pr_number or not pr_created_at:
        return None

    try:
        response = await http_client.get(
            f"/repos/{owner}/{repo}/pulls/{pr_number}/reviews",
            params={"per_page": 100},
        )

        if response.status_code != 200:
            return None

        reviews = response.json()
        if not reviews:
            return None

        pr_created = datetime.fromisoformat(pr_created_at.replace("Z", "+00:00"))

        first_review_time = None
        for review in reviews:
            submitted_at = review.get("submitted_at")
            if submitted_at:
                review_time = datetime.fromisoformat(submitted_at.replace("Z", "+00:00"))
                if review_time > pr_created:
                    if first_review_time is None or review_time < first_review_time:
                        first_review_time = review_time

        if first_review_time is None:
            return None

        delta = first_review_time - pr_created
        hours = delta.total_seconds() / 3600
        return hours

    except Exception:
        return None
