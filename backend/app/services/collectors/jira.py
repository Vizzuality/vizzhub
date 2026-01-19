"""
Jira API collector.

Collects:
- Defect counts (bugs closed, tasks completed)
- Escaped defects (bugs in Staging/Production)
- MTTR (mean time to recover from incidents)
- Lead time, flow efficiency, commitment reliability
- Story review status

Supports both OAuth 2.0 and legacy API token authentication.
"""

import re
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import ConfigurationError
from app.services.collectors.base import BaseCollector
from app.services.oauth_service import OAuthService


class JiraCollector(BaseCollector):
    """Collects metrics from Jira API."""

    def __init__(self, db: AsyncSession | None = None) -> None:
        settings = get_settings()
        self.settings = settings
        self.db = db
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get authenticated HTTP client using OAuth or legacy auth."""
        if self._client is None:
            # Try OAuth first if database session is available
            headers = {"Accept": "application/json"}
            auth = None
            base_url = None

            if self.db:
                # Try to get OAuth token
                oauth_token = await OAuthService.get_valid_jira_token(self.db)
                if oauth_token:
                    # Get site info for base URL
                    site_info = await OAuthService.get_jira_site_info(self.db)
                    if site_info and site_info.get("cloud_id"):
                        cloud_id = site_info["cloud_id"]
                        base_url = f"https://api.atlassian.com/ex/jira/{cloud_id}"
                        headers["Authorization"] = f"Bearer {oauth_token}"

            # Fallback to legacy API token auth
            if not base_url and self.settings.jira_base_url:
                base_url = self.settings.jira_base_url
                auth = (self.settings.jira_email, self.settings.jira_api_token)

            if not base_url:
                # Check if OAuth is configured but not authorized
                if self.settings.jira_oauth_client_id:
                    raise ConfigurationError(
                        "Jira OAuth is configured but not authorized. "
                        "Please complete the OAuth flow at /api/oauth/jira/authorize"
                    )
                else:
                    raise ConfigurationError(
                        "No Jira authentication configured. "
                        "Either set up OAuth or provide JIRA_BASE_URL, JIRA_EMAIL, and JIRA_API_TOKEN"
                    )

            self._client = httpx.AsyncClient(
                base_url=base_url,
                auth=auth,
                headers=headers,
                timeout=30.0,
            )

        return self._client

    async def test_connection(self) -> bool:
        try:
            client = await self._get_client()
            # Use serverInfo endpoint which works with read:jira-work scopes
            response = await client.get("/rest/api/3/serverInfo")
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

    def _validate_project_key(self, project_key: str) -> None:
        """
        Validate project key format to prevent JQL injection.

        Args:
            project_key: Jira project key to validate

        Raises:
            ValueError: If project key contains invalid characters
        """
        # Jira project keys: letters (upper/lowercase), numbers, hyphens, underscores
        # Typically 2-10 characters
        if not re.match(r"^[A-Za-z0-9_-]{1,20}$", project_key):
            raise ValueError(
                f"Invalid project key format: {project_key}. "
                "Project keys must contain only letters, numbers, hyphens, and underscores."
            )

    async def _count_issues(
        self, client: httpx.AsyncClient, project_key: str, jql_filter: str
    ) -> int:
        """Count issues matching a JQL query using approximate-count endpoint."""
        # Validate project key to prevent JQL injection
        self._validate_project_key(project_key)

        # Use quoted project key for safety
        jql = f'project = "{project_key}" AND {jql_filter}'
        try:
            response = await client.post(
                "/rest/api/3/search/approximate-count",
                json={"jql": jql},
            )
            if response.status_code == 200:
                # The approximate-count endpoint returns {"count": N}
                result = response.json()
                return result.get("count", 0) if isinstance(result, dict) else result
            else:
                # Log error for debugging
                import logging
                logging.warning(
                    f"JQL query failed (status {response.status_code}): {jql}\n"
                    f"Response: {response.text[:500]}"
                )
        except Exception as e:
            import logging
            logging.warning(f"JQL query exception: {jql}\nError: {e}")
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
        total = await self._count_issues(client, project_key, "type = Story")
        with_reviewer = await self._count_issues(
            client, project_key, "type = Story AND 'Reviewer' IS NOT EMPTY"
        )
        return {"total": total, "with_reviewer": with_reviewer}

    async def close(self) -> None:
        if self._client:
            await self._client.aclose()
            self._client = None
