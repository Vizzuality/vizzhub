"""
Shared Jira API client.

Handles authentication (OAuth 2.0 or legacy API token) and provides
common methods for querying Jira APIs.
"""

import re

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.exceptions import ConfigurationError
from app.services.oauth_service import OAuthService


class JiraClient:
    """Authenticated HTTP client for Jira API."""

    def __init__(self, db: AsyncSession | None = None) -> None:
        self.settings = get_settings()
        self.db = db
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get authenticated HTTP client using OAuth or legacy auth."""
        if self._client is None:
            headers = {"Accept": "application/json"}
            auth = None
            base_url = None

            if self.db:
                oauth_token = await OAuthService.get_valid_jira_token(self.db)
                if oauth_token:
                    site_info = await OAuthService.get_jira_site_info(self.db)
                    if site_info and site_info.get("cloud_id"):
                        cloud_id = site_info["cloud_id"]
                        base_url = f"https://api.atlassian.com/ex/jira/{cloud_id}"
                        headers["Authorization"] = f"Bearer {oauth_token}"

            if not base_url and self.settings.jira_base_url:
                base_url = self.settings.jira_base_url
                auth = (self.settings.jira_email, self.settings.jira_api_token)

            if not base_url:
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
        """Test if connection to Jira is working."""
        try:
            client = await self._get_client()
            response = await client.get("/rest/api/3/serverInfo")
            return response.status_code == 200
        except Exception:
            return False

    def validate_project_key(self, project_key: str) -> None:
        """
        Validate project key format to prevent JQL injection.

        Raises:
            ValueError: If project key contains invalid characters
        """
        if not re.match(r"^[A-Za-z0-9_-]{1,20}$", project_key):
            raise ValueError(
                f"Invalid project key format: {project_key}. "
                "Project keys must contain only letters, numbers, hyphens, and underscores."
            )

    async def count_issues(self, project_key: str, jql_filter: str) -> int:
        """
        Count issues matching a JQL query using approximate-count endpoint.

        Args:
            project_key: Jira project key (e.g., "PROJ")
            jql_filter: Additional JQL conditions (e.g., "type = Bug")

        Returns:
            Count of matching issues
        """
        self.validate_project_key(project_key)

        jql = f'project = "{project_key}" AND {jql_filter}'
        client = await self._get_client()

        try:
            response = await client.post(
                "/rest/api/3/search/approximate-count",
                json={"jql": jql},
            )
            if response.status_code == 200:
                result = response.json()
                return result.get("count", 0) if isinstance(result, dict) else result
            else:
                import logging

                logging.warning(
                    f"JQL query failed (status {response.status_code}): {jql}\n"
                    f"Response: {response.text[:500]}"
                )
        except Exception as e:
            import logging

            logging.warning(f"JQL query exception: {jql}\nError: {e}")

        return 0

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
