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
from datetime import datetime, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.collectors.github.client import GitHubClient

logger = logging.getLogger(__name__)

DAYS_THRESHOLD = 30


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
    threshold_date = now - __import__("datetime").timedelta(days=DAYS_THRESHOLD)

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


async def _get_dependabot_alerts(
    client: "GitHubClient", owner: str, repo: str
) -> list[dict] | None:
    """
    Get open high/critical severity Dependabot alerts.

    Returns None if Dependabot is not enabled or access is denied.
    Note: Dependabot API uses cursor-based pagination, not page numbers.
    """
    http_client = await client.get_client()
    all_alerts: list[dict] = []
    per_page = 100
    cursor: str | None = None

    while True:
        try:
            params: dict = {
                "state": "open",
                "severity": "high,critical",
                "per_page": per_page,
            }
            if cursor:
                params["after"] = cursor

            response = await http_client.get(
                f"/repos/{owner}/{repo}/dependabot/alerts",
                params=params,
            )

            if response.status_code == 403:
                # Dependabot alerts not enabled or no access
                return None

            if response.status_code == 404:
                # Repository not found or Dependabot not available
                return None

            if response.status_code != 200:
                return None

            alerts = response.json()
            if not alerts:
                break

            all_alerts.extend(alerts)

            # Check for next page via Link header
            link_header = response.headers.get("Link", "")
            if 'rel="next"' not in link_header:
                break

            # Extract cursor from Link header
            # Format: <url?after=cursor>; rel="next"
            import re
            match = re.search(r'after=([^&>]+)', link_header)
            if match:
                cursor = match.group(1)
            else:
                break

        except Exception as e:
            logger.warning("Failed to fetch Dependabot alerts for %s/%s: %s", owner, repo, e)
            return None

    return all_alerts
