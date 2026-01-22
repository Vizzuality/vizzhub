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

    releases = await _get_releases(client, owner, repo, include_prereleases)

    cutoff_date = datetime.now(timezone.utc) - timedelta(days=LOOKBACK_DAYS)

    releases_in_period = [
        r for r in releases
        if _parse_release_date(r) >= cutoff_date
    ]

    release_count = len(releases_in_period)

    frequency = release_count / LOOKBACK_DAYS if LOOKBACK_DAYS > 0 else 0

    return {
        "deployment_frequency": round(frequency, 4),
        "release_count_90d": release_count,
    }


async def _get_releases(
    client: "GitHubClient",
    owner: str,
    repo: str,
    include_prereleases: bool = True,
    max_results: int = 200,
) -> list[dict]:
    """Get releases from repository."""
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
                if release.get("draft"):
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


def _parse_release_date(release: dict) -> datetime:
    """Parse the release published date."""
    published_at = release.get("published_at")
    if published_at:
        return datetime.fromisoformat(published_at.replace("Z", "+00:00"))
    created_at = release.get("created_at")
    if created_at:
        return datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    return datetime.min.replace(tzinfo=timezone.utc)
