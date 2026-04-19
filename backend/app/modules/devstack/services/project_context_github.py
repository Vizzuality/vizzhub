"""GitHub I/O for per-project CLAUDE.md files in the private monorepo.

Two responsibilities: (1) fetch blobs by HEAD or by explicit SHA, and
(2) push commits via the Git Data API with optimistic locking. No merge
logic — all merge intelligence is LLM-side in the skill.
"""

import base64

import httpx


GITHUB_API = "https://api.github.com"


class NotFoundError(Exception):
    """Slug folder / CLAUDE.md / blob does not exist."""


class NoContentError(Exception):
    """Folder exists but has no CLAUDE.md at HEAD."""


class FetchError(Exception):
    """Generic GitHub API read failure (network, auth, quota)."""


class CommitError(Exception):
    """GitHub rejected the push (write path)."""


class ProjectContextGitHubClient:
    """Thin wrapper around GitHub's REST + Git Data APIs.

    One instance per request — do not share across async tasks without
    care. The httpx.AsyncClient is created per method call for simplicity;
    optimise later if needed.
    """

    def __init__(
        self,
        *,
        repo: str,
        token: str,
        committer_name: str,
        committer_email: str,
    ):
        self.repo = repo
        self.token = token
        self.committer_name = committer_name
        self.committer_email = committer_email

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def fetch_head(self, slug: str) -> tuple[str, str]:
        """Return (content, sha) of `<slug>/CLAUDE.md` at the default branch."""
        url = f"{GITHUB_API}/repos/{self.repo}/contents/{slug}/CLAUDE.md"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, headers=self._headers())

        if resp.status_code == 404:
            raise NotFoundError(slug)
        if resp.status_code >= 400:
            raise FetchError(f"GitHub returned {resp.status_code}: {resp.text}")

        data = resp.json()
        if data.get("encoding") != "base64":
            raise FetchError(f"Unexpected encoding: {data.get('encoding')}")
        content = base64.b64decode(data["content"]).decode("utf-8")
        return content, data["sha"]

    async def fetch_at_sha(self, blob_sha: str) -> str:
        """Return the content of a specific blob by SHA (immutable in Git)."""
        url = f"{GITHUB_API}/repos/{self.repo}/git/blobs/{blob_sha}"
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.get(url, headers=self._headers())

        if resp.status_code == 404:
            raise NotFoundError(blob_sha)
        if resp.status_code >= 400:
            raise FetchError(f"GitHub returned {resp.status_code}: {resp.text}")

        data = resp.json()
        if data.get("encoding") != "base64":
            raise FetchError(f"Unexpected encoding: {data.get('encoding')}")
        return base64.b64decode(data["content"]).decode("utf-8")
