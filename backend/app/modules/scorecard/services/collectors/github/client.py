"""
Shared GitHub API client.

Handles authentication via Personal Access Token and provides
common methods for querying GitHub APIs.
"""

import re

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConfigurationError
from app.modules.scorecard.services.collectors.utils import HTTP_CLIENT_TIMEOUT


class GitHubClient:
    """Authenticated HTTP client for GitHub API."""

    def __init__(self, db: AsyncSession | None = None, token: str | None = None) -> None:
        self._db = db
        self._token = token
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get authenticated HTTP client."""
        if self._client is None:
            token = self._token or await self._get_token_from_db()
            if not token:
                raise ConfigurationError(
                    "GitHub token not configured. Set token via Admin > Integrations."
                )

            headers = {
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": "2022-11-28",
            }

            self._client = httpx.AsyncClient(
                base_url="https://api.github.com",
                headers=headers,
                timeout=HTTP_CLIENT_TIMEOUT,
            )

        return self._client

    async def _get_token_from_db(self) -> str | None:
        """Read GitHub token from DB via IntegrationTokenService."""
        if self._db is None:
            return None
        from app.core.services.integration_token_service import IntegrationTokenService

        return await IntegrationTokenService.get_token(self._db, "github")

    async def get_client(self) -> httpx.AsyncClient:
        """Get the authenticated HTTP client (public method)."""
        return await self._get_client()

    def validate_repo_slug(self, repo_slug: str) -> tuple[str, str]:
        """
        Validate and parse repo slug format.

        Args:
            repo_slug: Repository in "owner/repo" format

        Returns:
            Tuple of (owner, repo)

        Raises:
            ValueError: If format is invalid
        """
        if not repo_slug or "/" not in repo_slug:
            raise ValueError(f"Invalid repo format: {repo_slug}. Expected 'owner/repo' format.")

        parts = repo_slug.split("/")
        if len(parts) != 2:
            raise ValueError(f"Invalid repo format: {repo_slug}. Expected 'owner/repo' format.")

        owner, repo = parts[0].strip(), parts[1].strip()

        if not re.match(r"^[A-Za-z0-9_.-]+$", owner):
            raise ValueError(f"Invalid owner format: {owner}")
        if not re.match(r"^[A-Za-z0-9_.-]+$", repo):
            raise ValueError(f"Invalid repo format: {repo}")

        return owner, repo

    async def test_connection(self) -> bool:
        """Test if connection to GitHub is working."""
        try:
            client = await self._get_client()
            response = await client.get("/user")
            return response.status_code == 200
        except Exception:
            return False

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None
