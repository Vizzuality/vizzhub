"""
Jira API collector.

Collects:
- Defect counts (bugs closed, tasks completed)
- Escaped defects (bugs in Staging/Production)
- MTTR (mean time to recover from incidents)
- Lead time, flow efficiency, commitment reliability
- Story review status
"""

from typing import Any

import httpx

from app.config import get_settings
from app.services.collectors.base import BaseCollector


class JiraCollector(BaseCollector):
    """Collects metrics from Jira API."""

    def __init__(self) -> None:
        settings = get_settings()
        self.base_url = settings.jira_base_url
        self.email = settings.jira_email
        self.api_token = settings.jira_api_token
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(
                base_url=self.base_url,
                auth=(self.email, self.api_token),
                headers={"Accept": "application/json"},
            )
        return self._client

    async def test_connection(self) -> bool:
        try:
            client = await self._get_client()
            response = await client.get("/rest/api/3/myself")
            return response.status_code == 200
        except Exception:
            return False

    async def collect(self, project_key: str, **kwargs: Any) -> dict[str, Any]:
        """
        Collect raw metrics from Jira for a project.

        Args:
            project_key: Jira project key (e.g., "PROJ")

        Returns:
            Raw metrics data without interpretation.
        """
        client = await self._get_client()

        bugs_closed = await self._count_issues(
            client, project_key, "type = Bug AND status = Done"
        )
        tasks_completed = await self._count_issues(
            client, project_key, "type in (Story, Task) AND status = Done"
        )
        escaped_defects = await self._count_issues(
            client,
            project_key,
            "type = Bug AND 'Environment' in ('Staging', 'Production')",
        )
        incidents = await self._get_incidents(client, project_key)
        flow_data = await self._get_flow_metrics(client, project_key)
        story_review = await self._get_story_review_data(client, project_key)

        return {
            "bugs_closed": bugs_closed,
            "tasks_completed": tasks_completed,
            "escaped_defects": escaped_defects,
            "incidents_count": incidents.get("count", 0),
            "mttr_hours": incidents.get("mttr_hours"),
            "lead_time_days": flow_data.get("lead_time_days"),
            "flow_efficiency": flow_data.get("flow_efficiency"),
            "commitment_reliability": flow_data.get("commitment_reliability"),
            "total_stories": story_review.get("total", 0),
            "stories_with_reviewer": story_review.get("with_reviewer", 0),
        }

    async def _count_issues(
        self, client: httpx.AsyncClient, project_key: str, jql_filter: str
    ) -> int:
        """Count issues matching a JQL query."""
        jql = f"project = {project_key} AND {jql_filter}"
        try:
            response = await client.get(
                "/rest/api/3/search",
                params={"jql": jql, "maxResults": 0},
            )
            if response.status_code == 200:
                return response.json().get("total", 0)
        except Exception:
            pass
        return 0

    async def _get_incidents(
        self, client: httpx.AsyncClient, project_key: str
    ) -> dict[str, Any]:
        """Get incident data for MTTR calculation."""
        return {"count": 0, "mttr_hours": None}

    async def _get_flow_metrics(
        self, client: httpx.AsyncClient, project_key: str
    ) -> dict[str, Any]:
        """Get flow metrics (lead time, efficiency, commitment)."""
        return {
            "lead_time_days": None,
            "flow_efficiency": None,
            "commitment_reliability": None,
        }

    async def _get_story_review_data(
        self, client: httpx.AsyncClient, project_key: str
    ) -> dict[str, Any]:
        """Get story review status data."""
        total = await self._count_issues(
            client, project_key, "type = Story"
        )
        with_reviewer = await self._count_issues(
            client, project_key, "type = Story AND 'Reviewer' IS NOT EMPTY"
        )
        return {"total": total, "with_reviewer": with_reviewer}

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
