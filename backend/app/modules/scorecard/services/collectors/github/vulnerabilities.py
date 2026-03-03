"""
vulnerabilities - GitHub Dependabot security alerts

== SPEC ==

Formula:
    high_severity_vulns = count of open high/critical severity alerts older than 30 days

Definition:
    Measures security debt by counting high and critical severity vulnerabilities
    that have remained unaddressed for more than 30 days.

Data Source:
    GitHub API:
    - GET /repos/{owner}/{repo}/dependabot/alerts?state=open&severity=high,critical

Target:
    0 vulnerabilities (high_vuln_t)

Normalization:
    Strict zero target: if value > 0, score heavily penalized
    Used in P_risk dimension

Edge Cases:
    - Dependabot not enabled: return 0 (assume no known vulns)
    - API access denied (403): return 0 with warning
    - No alerts: return 0

== END SPEC ==
"""

import logging
import re
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.modules.scorecard.services.collectors.github.client import GitHubClient

logger = logging.getLogger(__name__)

DAYS_THRESHOLD = 30
_CURSOR_PATTERN = re.compile(r'after=([^&>]+)')


async def collect_vulnerabilities(client: "GitHubClient", repo_slug: str) -> dict:
    """
    Collect high-severity vulnerability metrics from GitHub Dependabot.

    Args:
        client: Authenticated GitHubClient instance
        repo_slug: Repository in "owner/repo" format

    Returns:
        dict with high_severity_vulns count and details
    """
    owner, repo = client.validate_repo_slug(repo_slug)

    alerts = await _get_dependabot_alerts(client, owner, repo)

    if alerts is None:
        return {
            "high_severity_vulns": 0,
            "high_severity_vulns_total": 0,
            "vulns_older_than_30d": 0,
        }

    now = datetime.now(timezone.utc)
    threshold_date = now - timedelta(days=DAYS_THRESHOLD)

    older_than_30d = []
    for alert in alerts:
        created_at_str = alert.get("created_at")
        if created_at_str:
            created_at = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
            if created_at < threshold_date:
                older_than_30d.append(alert)

    return {
        "high_severity_vulns": len(older_than_30d),
        "high_severity_vulns_total": len(alerts),
        "vulns_older_than_30d": len(older_than_30d),
    }


def _extract_next_cursor(link_header: str) -> str | None:
    """Extract pagination cursor from Link header."""
    if 'rel="next"' not in link_header:
        return None
    match = _CURSOR_PATTERN.search(link_header)
    return match.group(1) if match else None


def _is_access_denied(status_code: int) -> bool:
    """Check if response indicates access denied or not available."""
    return status_code in (403, 404)


async def _get_dependabot_alerts(
    client: "GitHubClient", owner: str, repo: str
) -> list[dict] | None:
    """Get open high/critical severity Dependabot alerts."""
    http_client = await client.get_client()
    all_alerts: list[dict] = []
    cursor: str | None = None

    while True:
        try:
            params: dict = {"state": "open", "severity": "high,critical", "per_page": 100}
            if cursor:
                params["after"] = cursor

            response = await http_client.get(
                f"/repos/{owner}/{repo}/dependabot/alerts",
                params=params,
            )

            if _is_access_denied(response.status_code) or response.status_code != 200:
                return None

            alerts = response.json()
            if not alerts:
                break

            all_alerts.extend(alerts)

            cursor = _extract_next_cursor(response.headers.get("Link", ""))
            if not cursor:
                break

        except Exception as e:
            logger.warning("Failed to fetch Dependabot alerts for %s/%s: %s", owner, repo, e)
            return None

    return all_alerts
