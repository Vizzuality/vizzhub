"""
Jira API collector.

Orchestrates collection of all Jira-sourced indicators.
Individual indicator logic is in app.services.collectors.jira.*

Supports both OAuth 2.0 and legacy API token authentication.
"""

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.collectors.base import BaseCollector
from app.services.collectors.jira.client import JiraClient
from app.services.collectors.jira.defect_density import collect_defect_density


class JiraCollector(BaseCollector):
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
        # Validate project key once
        self._jira_client.validate_project_key(project_key)

        # Collect defect density metrics (migrated to new module)
        defect_data = await collect_defect_density(self._jira_client, project_key)

        # Collect escaped defects (TODO: migrate to separate module)
        escaped_defects = await self._jira_client.count_issues(
            project_key,
            "type = Bug AND 'Environment' in ('Staging', 'Production')",
        )

        # Collect other metrics (TODO: migrate to separate modules)
        incidents = await self._get_incidents(project_key)
        flow_data = await self._get_flow_metrics(project_key)
        story_review = await self._get_story_review_data(project_key)

        return {
            "bugs_closed": defect_data["bugs_closed"],
            "tasks_completed": defect_data["tasks_completed"],
            "escaped_defects": escaped_defects,
            "incidents_count": incidents.get("count", 0),
            "mttr_hours": incidents.get("mttr_hours"),
            "lead_time_days": flow_data.get("lead_time_days"),
            "flow_efficiency": flow_data.get("flow_efficiency"),
            "commitment_reliability": flow_data.get("commitment_reliability"),
            "total_stories": story_review.get("total", 0),
            "stories_with_reviewer": story_review.get("with_reviewer", 0),
        }

    async def _get_incidents(self, project_key: str) -> dict[str, Any]:
        """Get incident data for MTTR calculation."""
        return {"count": 0, "mttr_hours": None}

    async def _get_flow_metrics(self, project_key: str) -> dict[str, Any]:
        """Get flow metrics (lead time, efficiency, commitment)."""
        return {
            "lead_time_days": None,
            "flow_efficiency": None,
            "commitment_reliability": None,
        }

    async def _get_story_review_data(self, project_key: str) -> dict[str, Any]:
        """Get story review status data."""
        total = await self._jira_client.count_issues(project_key, "type = Story")
        with_reviewer = await self._jira_client.count_issues(
            project_key, "type = Story AND 'Reviewer' IS NOT EMPTY"
        )
        return {"total": total, "with_reviewer": with_reviewer}

    async def close(self) -> None:
        """Close the HTTP client."""
        await self._jira_client.close()
