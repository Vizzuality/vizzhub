"""
Shared Jira API client.

Handles authentication (OAuth 2.0 or legacy API token) and provides
common methods for querying Jira APIs.
"""

import logging
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

    async def _try_oauth_auth(self) -> tuple[str | None, str | None]:
        """Try to get OAuth credentials. Returns (base_url, bearer_token) or (None, None)."""
        if not self.db:
            return None, None
        oauth_token = await OAuthService.get_valid_jira_token(self.db)
        if not oauth_token:
            return None, None
        site_info = await OAuthService.get_jira_site_info(self.db)
        if not site_info or not site_info.get("cloud_id"):
            return None, None
        cloud_id = site_info["cloud_id"]
        return f"https://api.atlassian.com/ex/jira/{cloud_id}", oauth_token

    def _try_legacy_auth(self) -> tuple[str | None, tuple[str, str] | None]:
        """Try to get legacy auth credentials. Returns (base_url, auth_tuple) or (None, None)."""
        if not self.settings.jira_base_url:
            return None, None
        return self.settings.jira_base_url, (self.settings.jira_email, self.settings.jira_api_token)

    def _raise_config_error(self) -> None:
        """Raise appropriate configuration error."""
        if self.settings.jira_oauth_client_id:
            raise ConfigurationError(
                "Jira OAuth is configured but not authorized. "
                "Please complete the OAuth flow at /api/oauth/jira/authorize"
            )
        raise ConfigurationError(
            "No Jira authentication configured. "
            "Either set up OAuth or provide JIRA_BASE_URL, JIRA_EMAIL, and JIRA_API_TOKEN"
        )

    async def _get_client(self) -> httpx.AsyncClient:
        """Get authenticated HTTP client using OAuth or legacy auth."""
        if self._client is not None:
            return self._client

        headers = {"Accept": "application/json"}
        auth = None

        base_url, bearer_token = await self._try_oauth_auth()
        if bearer_token:
            headers["Authorization"] = f"Bearer {bearer_token}"

        if not base_url:
            base_url, auth = self._try_legacy_auth()

        if not base_url:
            self._raise_config_error()

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
                logging.warning(
                    f"JQL query failed (status {response.status_code}): {jql}\n"
                    f"Response: {response.text[:500]}"
                )
        except Exception as e:
            logging.warning(f"JQL query exception: {jql}\nError: {e}")

        return 0

    async def get_client(self) -> httpx.AsyncClient:
        """Get the authenticated HTTP client (public method for indicator modules)."""
        return await self._get_client()

    async def search_issues(
        self,
        project_key: str,
        jql_filter: str,
        fields: list[str] | None = None,
        max_results: int = 100,
        skip_project_prefix: bool = False,
        expand: list[str] | None = None,
    ) -> list[dict]:
        """
        Search issues matching a JQL query.

        Args:
            project_key: Jira project key (e.g., "PROJ")
            jql_filter: JQL conditions
            fields: Fields to return (default: key only)
            max_results: Maximum number of issues to return
            skip_project_prefix: If True, don't prepend project clause to JQL
            expand: List of expansions (e.g., ["changelog"])

        Returns:
            List of issue dictionaries
        """
        self.validate_project_key(project_key)

        if skip_project_prefix:
            jql = jql_filter
        else:
            jql = f'project = "{project_key}" AND {jql_filter}'

        client = await self._get_client()
        all_issues: list[dict] = []
        page_token = None

        try:
            while len(all_issues) < max_results:
                body: dict = {
                    "jql": jql,
                    "fields": fields or ["key"],
                    "maxResults": min(100, max_results - len(all_issues)),
                }
                if expand:
                    body["expand"] = ",".join(expand)
                if page_token:
                    body["pageToken"] = page_token

                response = await client.post("/rest/api/3/search/jql", json=body)

                if response.status_code != 200:
                    break

                data = response.json()
                issues = data.get("issues", [])
                all_issues.extend(issues)

                page_token = data.get("nextPageToken")
                if not page_token or not issues:
                    break

        except Exception as e:
            logging.warning(f"Search issues exception: {jql}\nError: {e}")

        return all_issues

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
