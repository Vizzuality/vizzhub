"""
Jira API collector.

Orchestrates collection of all Jira-sourced indicators.
Individual indicator logic is in separate modules within this package.

Supports both OAuth 2.0 and legacy API token authentication.
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.collectors.jira.client import JiraClient
from app.services.collectors.jira.commitment_reliability import (
    collect_commitment_reliability,
)
from app.services.collectors.jira.defect_density import collect_defect_density
from app.services.collectors.jira.escaped_rate import collect_escaped_rate
from app.services.collectors.jira.flow_efficiency import collect_flow_efficiency
from app.services.collectors.jira.lead_time import collect_lead_time
from app.services.collectors.jira.mttr import collect_mttr
from app.services.collectors.jira.story_review_ratio import collect_story_review_ratio


class JiraCollector:
    """Collects metrics from Jira API."""

    def __init__(self, db: AsyncSession | None = None) -> None:
        self._jira_client = JiraClient(db)

    async def test_connection(self) -> bool:
        """Test if connection to Jira is working."""
        return await self._jira_client.test_connection()

    async def collect(self, project_key: str, **kwargs: Any) -> dict[str, Any]:
        """
        Collect raw metrics from Jira for a project.

        Args:
            project_key: Jira project key (e.g., "PROJ")

        Returns:
            Raw metrics data without interpretation.
        """
        self._jira_client.validate_project_key(project_key)

        defect_data = await collect_defect_density(self._jira_client, project_key)
        escaped_data = await collect_escaped_rate(self._jira_client, project_key)
        mttr_data = await collect_mttr(self._jira_client, project_key)
        story_review_data = await collect_story_review_ratio(
            self._jira_client, project_key
        )
        commitment_data = await collect_commitment_reliability(
            self._jira_client, project_key
        )
        lead_time_data = await collect_lead_time(self._jira_client, project_key)
        flow_data = await collect_flow_efficiency(self._jira_client, project_key)

        return {
            # defect_density
            "bugs_total": defect_data["bugs_total"],
            "tasks_completed": defect_data["tasks_completed"],
            # escaped_rate
            "escaped_defects": escaped_data["escaped_defects"],
            # mttr
            "incidents_count": mttr_data["incidents_count"],
            "mttr_hours": mttr_data["mttr_hours"],
            # story_review_ratio
            "total_stories": story_review_data["total_stories"],
            "stories_with_reviewer": story_review_data["stories_with_reviewer"],
            # commitment_reliability
            "commitment_reliability": commitment_data["commitment_reliability"],
            # lead_time
            "lead_time_days": lead_time_data["lead_time_days"],
            # flow_efficiency
            "flow_efficiency": flow_data["flow_efficiency"],
        }

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._jira_client.close()
