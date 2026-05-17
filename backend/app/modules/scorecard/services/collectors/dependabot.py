"""Dependabot alerts collector.

Fetches security alerts from GitHub's Dependabot API, filtering for
high and critical severity vulnerabilities only.
"""

from typing import Any

import httpx


class DependabotCollector:
    """Collector for GitHub Dependabot alerts."""

    GITHUB_API = "https://api.github.com"
    TARGET_SEVERITIES = {"critical", "high"}

    @staticmethod
    async def fetch_alerts(
        repo: str,
        token: str,
    ) -> list[dict[str, Any]]:
        """
        Fetch open high/critical Dependabot alerts for a repo.

        Args:
            repo: Repository in "owner/repo" format
            token: GitHub personal access token

        Returns:
            List of alert dictionaries with high/critical severity
        """
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{DependabotCollector.GITHUB_API}/repos/{repo}/dependabot/alerts",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
                params={"state": "open", "per_page": 100},
            )

            if response.status_code != 200:
                return []

            alerts = response.json()

            return [
                alert
                for alert in alerts
                if alert.get("security_vulnerability", {}).get("severity", "").lower()
                in DependabotCollector.TARGET_SEVERITIES
            ]

    @staticmethod
    def extract_alert_info(alert: dict[str, Any]) -> dict[str, Any]:
        """
        Extract relevant info from a Dependabot alert.

        Args:
            alert: Raw alert dictionary from GitHub API

        Returns:
            Dictionary with extracted fields:
            - github_alert_id: Alert number
            - package_name: Vulnerable package name
            - severity: Vulnerability severity level
            - cve_id: CVE identifier if available
        """
        vuln = alert.get("security_vulnerability", {})
        advisory = alert.get("security_advisory", {})

        dependency = alert.get("dependency", {})

        return {
            "github_alert_id": alert.get("number"),
            "package_name": vuln.get("package", {}).get("name"),
            "severity": vuln.get("severity"),
            "cve_id": next(
                (i["value"] for i in advisory.get("identifiers", []) if i["type"] == "CVE"),
                None,
            ),
            "manifest_path": dependency.get("manifest_path"),
        }
