"""
deployment_frequency - Deployment frequency metrics (DORA)

== SPEC ==

Formula:
    deployment_frequency = count(releases in 90 days) / 90

Definition:
    Measures how frequently the team deploys to production by counting
    releases in the last 90 days and calculating a daily rate.

Data Source:
    GitHub API:
    - GET /repos/{owner}/{repo}/releases

Target:
    deployment_freq_t from config (default: 1 per day)

Normalization:
    Higher is better → min(1, value / 1)

Edge Cases:
    - No releases: return 0 (score 0)
    - Draft releases: exclude
    - Prereleases: include (configurable)

DORA Benchmarks:
    - Elite: Multiple per day (>1)
    - High: Weekly-daily (0.14-1)
    - Medium: Monthly-weekly (0.03-0.14)
    - Low: Monthly+ (<0.03)

== END SPEC ==
"""

from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from app.services.collectors.github.utils import get_releases, parse_release_date

if TYPE_CHECKING:
    from app.services.collectors.github.client import GitHubClient

LOOKBACK_DAYS = 90


async def collect_deployment_frequency(
    client: "GitHubClient",
    repo_slug: str,
    include_prereleases: bool = True,
) -> dict:
    """
    Collect deployment frequency metrics from GitHub.

    Args:
        client: Authenticated GitHubClient instance
        repo_slug: Repository in "owner/repo" format
        include_prereleases: Whether to count prereleases

    Returns:
        dict with deployment_frequency and release_count_90d
    """
    owner, repo = client.validate_repo_slug(repo_slug)

    releases = await get_releases(
        client, owner, repo, include_prereleases=include_prereleases
    )

    cutoff_date = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)

    releases_in_period = [
        r for r in releases
        if parse_release_date(r) >= cutoff_date
    ]

    release_count = len(releases_in_period)

    frequency = release_count / LOOKBACK_DAYS if LOOKBACK_DAYS > 0 else 0

    return {
        "deployment_frequency": round(frequency, 4),
        "release_count_90d": release_count,
    }
