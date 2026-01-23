"""
GitHub API collector.

Orchestrates collection of all GitHub-sourced indicators.
Individual indicator logic is in separate modules within this package.
"""

from typing import Any

from app.services.collectors.github.change_failure_rate import (
    collect_change_failure_rate,
)
from app.services.collectors.github.client import GitHubClient
from app.services.collectors.github.deployment_frequency import (
    collect_deployment_frequency,
)
from app.services.collectors.github.pr_review import collect_pr_review
from app.services.collectors.github.pr_size import collect_pr_size
from app.services.collectors.github.review_turnaround import collect_review_turnaround
from app.services.collectors.github.vulnerabilities import collect_vulnerabilities


class GitHubCollector:
    """Collects metrics from GitHub API."""

    def __init__(self) -> None:
        self._client = GitHubClient()

    async def test_connection(self) -> bool:
        """Test if connection to GitHub is working."""
        return await self._client.test_connection()

    async def collect(self, repo_slug: str, **kwargs: Any) -> dict[str, Any]:
        """
        Collect raw metrics from GitHub for a repository.

        Args:
            repo_slug: Repository in "owner/repo" format

        Returns:
            Raw metrics data without interpretation.
        """
        self._client.validate_repo_slug(repo_slug)

        pr_review_data = await collect_pr_review(self._client, repo_slug)
        pr_size_data = await collect_pr_size(self._client, repo_slug)
        review_turnaround_data = await collect_review_turnaround(self._client, repo_slug)
        deployment_freq_data = await collect_deployment_frequency(self._client, repo_slug)
        cfr_data = await collect_change_failure_rate(self._client, repo_slug)
        vuln_data = await collect_vulnerabilities(self._client, repo_slug)

        return {
            # pr_review
            "prs_without_review": pr_review_data["prs_without_review"],
            "total_merged_prs": pr_review_data["total_merged_prs"],
            "pr_review_ratio": pr_review_data["pr_review_ratio"],
            # pr_size
            "pr_size_median": pr_size_data["pr_size_median"],
            # review_turnaround
            "review_turnaround_hours": review_turnaround_data["review_turnaround_hours"],
            # deployment_frequency
            "deployment_frequency": deployment_freq_data["deployment_frequency"],
            "release_count_90d": deployment_freq_data["release_count_90d"],
            # change_failure_rate
            "change_failure_rate": cfr_data["change_failure_rate"],
            "total_releases": cfr_data["total_releases"],
            "failed_releases": cfr_data["failed_releases"],
            # vulnerabilities
            "high_severity_vulns": vuln_data["high_severity_vulns"],
            "high_severity_vulns_total": vuln_data["high_severity_vulns_total"],
        }

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._client.close()
