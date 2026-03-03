"""
Jira API collector.

Orchestrates collection of all Jira-sourced indicators.
Individual indicator logic is in separate modules within this package.

Supports both OAuth 2.0 and legacy API token authentication.
"""

from datetime import date
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.scorecard.services.collectors.jira.client import JiraClient
from app.modules.scorecard.services.collectors.models import JiraCollectedMetrics
from app.modules.scorecard.services.collectors.jira.commitment_reliability import (
    collect_commitment_reliability,
)
from app.modules.scorecard.services.collectors.jira.defect_density import collect_defect_density
from app.modules.scorecard.services.collectors.jira.escaped_rate import collect_escaped_rate
from app.modules.scorecard.services.collectors.jira.lead_time import collect_lead_time
from app.modules.scorecard.services.collectors.jira.mttr import collect_mttr
from app.modules.scorecard.services.collectors.jira.post_contract_tasks import collect_post_contract_tasks
from app.modules.scorecard.services.collectors.jira.story_review_ratio import collect_story_review_ratio


class JiraCollector:
    """Collects metrics from Jira API."""

    def __init__(self, db: AsyncSession | None = None) -> None:
        self._jira_client = JiraClient(db)

    async def test_connection(self) -> bool:
        """Test if connection to Jira is working."""
        return await self._jira_client.test_connection()

    async def collect(self, project_key: str, **kwargs: Any) -> JiraCollectedMetrics:
        """
        Collect raw metrics from Jira for a project.

        Args:
            project_key: Jira project key (e.g., "PROJ")
            period_start: Optional start date for filtering (inclusive)
            period_end: Optional end date for filtering (inclusive)

        Returns:
            Raw metrics data without interpretation.
        """
        self._jira_client.validate_project_key(project_key)

        period_start: date | None = kwargs.get("period_start")
        period_end: date | None = kwargs.get("period_end")

        defect_data = await collect_defect_density(
            self._jira_client, project_key, period_start=period_start, period_end=period_end
        )
        escaped_data = await collect_escaped_rate(
            self._jira_client, project_key, period_start=period_start, period_end=period_end
        )
        mttr_data = await collect_mttr(
            self._jira_client, project_key, period_start=period_start, period_end=period_end
        )
        story_review_data = await collect_story_review_ratio(
            self._jira_client, project_key, period_start=period_start, period_end=period_end
        )
        commitment_data = await collect_commitment_reliability(
            self._jira_client, project_key, period_start=period_start, period_end=period_end
        )
        lead_time_data = await collect_lead_time(
            self._jira_client, project_key, period_start=period_start, period_end=period_end
        )
        post_contract_data = await collect_post_contract_tasks(
            self._jira_client, project_key, kwargs.get("end_date")
        )

        return JiraCollectedMetrics(
            bugs_total=defect_data["bugs_total"],
            tasks_completed=defect_data["tasks_completed"],
            escaped_defects=escaped_data["escaped_defects"],
            incidents_count=mttr_data["incidents_count"],
            mttr_hours=mttr_data["mttr_hours"],
            total_stories=story_review_data["total_stories"],
            stories_with_reviewer=story_review_data["stories_with_reviewer"],
            commitment_reliability=commitment_data["commitment_reliability"],
            committed_issues=commitment_data["committed_issues"],
            single_sprint_issues=commitment_data["single_sprint_issues"],
            multi_sprint_issues=commitment_data["multi_sprint_issues"],
            lead_time_days=lead_time_data["lead_time_days"],
            lead_time_sample_size=lead_time_data["sample_size"],
            post_contract_tasks=post_contract_data["post_contract_tasks"],
            post_contract_cutoff=post_contract_data["post_contract_cutoff"],
        )

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._jira_client.close()
