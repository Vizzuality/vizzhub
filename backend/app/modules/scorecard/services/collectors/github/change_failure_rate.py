"""
change_failure_rate - Change Failure Rate metrics (DORA)

== SPEC ==

Formula:
    change_failure_rate = (releases_followed_by_patch / total_releases) × 100

Definition:
    Measures the percentage of releases that required a follow-up patch
    or hotfix within 7 days, indicating deployment failures.

Data Source:
    GitHub API:
    - GET /repos/{owner}/{repo}/releases

Target:
    change_failure_rate_t from config (default: 15%)

Normalization:
    Lower is better → min(1, 15 / value)

Detection Heuristics:
    1. Semver: 1.2.3 → 1.2.4 within 7 days = failure
    2. Tag: v1.0.0 → v1.0.1 or v1.0.0-hotfix
    3. Name: contains "hotfix", "patch", "fix"

Edge Cases:
    - No releases: return None (neutral)
    - Single release: return 0%
    - Non-semver tags: name-based detection only

DORA Benchmarks (see dora._classify_change_failure_rate):
    - Elite: 0-5%
    - High: 5-10%
    - Medium: 10-15%
    - Low: >15%

== END SPEC ==
"""

import re
from datetime import date, timedelta
from typing import TYPE_CHECKING

from app.modules.scorecard.services.collectors.github.utils import get_releases, parse_release_date

if TYPE_CHECKING:
    from app.modules.scorecard.services.collectors.github.client import GitHubClient

PATCH_WINDOW_DAYS = 7
HOTFIX_PATTERNS = [
    r"\bhotfix\b",
    r"\bpatch\b",
    r"\bfix\b",
    r"\bugfix\b",
    r"\bemergency\b",
]


async def collect_change_failure_rate(
    client: "GitHubClient",
    repo_slug: str,
    period_start: date | None = None,
    period_end: date | None = None,
) -> dict:
    """
    Collect change failure rate metrics from GitHub.

    Args:
        client: Authenticated GitHubClient instance
        repo_slug: Repository in "owner/repo" format
        period_start: Optional start date for punctual filtering (inclusive)
        period_end: Optional end date for filtering releases

    Returns:
        dict with change_failure_rate, total_releases, failed_releases
    """
    owner, repo = client.validate_repo_slug(repo_slug)

    releases = await get_releases(
        client,
        owner,
        repo,
        include_prereleases=True,
        period_start=period_start,
        period_end=period_end,
    )

    if not releases:
        return {
            "change_failure_rate": None,
            "total_releases": 0,
            "failed_releases": 0,
        }

    if len(releases) == 1:
        return {
            "change_failure_rate": 0.0,
            "total_releases": 1,
            "failed_releases": 0,
        }

    releases_sorted = sorted(
        releases,
        key=lambda r: parse_release_date(r),
    )

    failed_releases = 0
    total_for_calculation = len(releases_sorted) - 1

    for i, release in enumerate(releases_sorted[:-1]):
        next_release = releases_sorted[i + 1]
        if _is_failure_response(release, next_release):
            failed_releases += 1

    if total_for_calculation <= 0:
        return {
            "change_failure_rate": 0.0,
            "total_releases": len(releases_sorted),
            "failed_releases": 0,
        }

    cfr = min((failed_releases / total_for_calculation) * 100, 100.0)

    return {
        "change_failure_rate": round(cfr, 1),
        "total_releases": len(releases_sorted),
        "failed_releases": failed_releases,
    }


def _is_failure_response(release: dict, next_release: dict) -> bool:
    """
    Determine if next_release is a failure response to release.

    A release is considered a failure response if:
    1. It happens within PATCH_WINDOW_DAYS days
    2. AND (it's a semver patch OR it contains hotfix keywords)
    """
    release_date = parse_release_date(release)
    next_date = parse_release_date(next_release)

    if next_date - release_date > timedelta(days=PATCH_WINDOW_DAYS):
        return False

    if _is_hotfix_by_name(next_release):
        return True

    if _is_semver_patch(release, next_release):
        return True

    return False


def _is_hotfix_by_name(release: dict) -> bool:
    """Check if release name or tag contains hotfix keywords."""
    name = (release.get("name") or "").lower()
    tag = (release.get("tag_name") or "").lower()
    body = (release.get("body") or "").lower()

    text_to_check = f"{name} {tag} {body}"

    for pattern in HOTFIX_PATTERNS:
        if re.search(pattern, text_to_check, re.IGNORECASE):
            return True

    return False


def _is_semver_patch(release: dict, next_release: dict) -> bool:
    """
    Check if next_release is a semver patch version of release.

    Examples:
    - 1.2.3 → 1.2.4 = patch (True)
    - 1.2.3 → 1.3.0 = minor (False)
    - 1.2.3 → 2.0.0 = major (False)
    - v1.2.3 → v1.2.4 = patch (True)
    """
    tag1 = release.get("tag_name") or ""
    tag2 = next_release.get("tag_name") or ""

    v1 = _parse_semver(tag1)
    v2 = _parse_semver(tag2)

    if v1 is None or v2 is None:
        return False

    major1, minor1, patch1 = v1
    major2, minor2, patch2 = v2

    return major1 == major2 and minor1 == minor2 and patch2 == patch1 + 1


def _parse_semver(tag: str) -> tuple[int, int, int] | None:
    """Parse a semver tag like v1.2.3 or 1.2.3 into (major, minor, patch)."""
    tag = tag.lstrip("v")

    match = re.match(r"^(\d+)\.(\d+)\.(\d+)", tag)
    if match:
        return int(match.group(1)), int(match.group(2)), int(match.group(3))

    return None
