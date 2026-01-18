"""
GitHub API collector.

Collects:
- PR review ratios
- PRs merged without review
- Total merged PRs
- High severity vulnerabilities from Dependabot (>30 days old)
"""

from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from app.config import get_settings
from app.services.collectors.base import BaseCollector


class GitHubCollector(BaseCollector):
    """Collects metrics from GitHub API."""

    def __init__(self) -> None:
        settings = get_settings()
        self.token = settings.github_token
        self.org = settings.github_org
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url="https://api.github.com",
                headers={
                    "Accept": "application/vnd.github+json",
                    "Authorization": f"Bearer {self.token}",
                    "X-GitHub-Api-Version": "2022-11-28",
                },
            )
        return self._client

    async def test_connection(self) -> bool:
        try:
            client = await self._get_client()
            response = await client.get("/user")
            return response.status_code == 200
        except Exception:
            return False

    async def collect(self, repo: str, **kwargs: Any) -> dict[str, Any]:
        """
        Collect raw metrics from GitHub for a repository.

        Args:
            repo: Repository in format "owner/repo"

        Returns:
            Raw metrics data without interpretation.
        """
        client = await self._get_client()

        pr_data = await self._get_pr_metrics(client, repo)
        vuln_data = await self._get_vulnerability_data(client, repo)

        total_merged = pr_data.get("total_merged", 0)
        prs_without_review = pr_data.get("without_review", 0)

        pr_review_ratio = None
        if total_merged > 0:
            pr_review_ratio = (total_merged - prs_without_review) / total_merged

        return {
            "prs_without_review": prs_without_review,
            "total_merged_prs": total_merged,
            "pr_review_ratio": pr_review_ratio,
            "high_severity_vulns": vuln_data.get("high_severity_count", 0),
        }

    async def _get_pr_metrics(
        self, client: httpx.AsyncClient, repo: str
    ) -> dict[str, Any]:
        """Get PR review metrics."""
        try:
            response = await client.get(
                f"/repos/{repo}/pulls",
                params={"state": "closed", "per_page": 100},
            )
            if response.status_code != 200:
                return {"total_merged": 0, "without_review": 0}

            prs = response.json()
            merged_prs = [pr for pr in prs if pr.get("merged_at")]
            total_merged = len(merged_prs)

            without_review = 0
            for pr in merged_prs:
                pr_number = pr["number"]
                reviews_response = await client.get(
                    f"/repos/{repo}/pulls/{pr_number}/reviews"
                )
                if reviews_response.status_code == 200:
                    reviews = reviews_response.json()
                    if not reviews:
                        without_review += 1

            return {"total_merged": total_merged, "without_review": without_review}
        except Exception:
            return {"total_merged": 0, "without_review": 0}

    async def _get_vulnerability_data(
        self, client: httpx.AsyncClient, repo: str
    ) -> dict[str, Any]:
        """Get Dependabot vulnerability data."""
        try:
            response = await client.get(
                f"/repos/{repo}/dependabot/alerts",
                params={"state": "open", "severity": "high,critical"},
            )
            if response.status_code != 200:
                return {"high_severity_count": 0}

            alerts = response.json()
            threshold_date = datetime.now(timezone.utc) - timedelta(days=30)

            old_high_severity = 0
            for alert in alerts:
                created_at = datetime.fromisoformat(
                    alert["created_at"].replace("Z", "+00:00")
                )
                if created_at < threshold_date:
                    old_high_severity += 1

            return {"high_severity_count": old_high_severity}
        except Exception:
            return {"high_severity_count": 0}

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
