"""
Shared GitHub API client.

Handles authentication via Personal Access Token and provides
common methods for querying GitHub APIs.
"""

import re

import httpx

from app.config import get_settings
from app.core.exceptions import ConfigurationError


class GitHubClient:
    """Authenticated HTTP client for GitHub API."""

    def __init__(self) -> None:
        self.settings = get_settings()
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Get authenticated HTTP client."""
        if self._client is None:
            if not self.settings.github_token:
                raise ConfigurationError(
                    "GitHub token not configured. "
                    "Set GITHUB_TOKEN in environment variables."
                )

            headers = {
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {self.settings.github_token}",
                "X-GitHub-Api-Version": "2022-11-28",
            }

            self._client = httpx.AsyncClient(
                base_url="https://api.github.com",
                headers=headers,
                timeout=30.0,
            )

        return self._client

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
            raise ValueError(
                f"Invalid repo format: {repo_slug}. "
                "Expected 'owner/repo' format."
            )

        parts = repo_slug.split("/")
        if len(parts) != 2:
            raise ValueError(
                f"Invalid repo format: {repo_slug}. "
                "Expected 'owner/repo' format."
            )

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
