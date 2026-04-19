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


class OptimisticLockError(Exception):
    """Remote blob SHA no longer matches the expected value.

    The caller must re-fetch the remote, re-run the LLM-mediated merge,
    and retry with the new expected_remote_sha.
    """

    def __init__(self, current_sha: str):
        super().__init__(f"Remote advanced to {current_sha}")
        self.current_sha = current_sha


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

    async def push(
        self,
        *,
        slug: str,
        content: str,
        expected_remote_sha: str,
        author_name: str,
        author_email: str,
        message: str,
    ) -> str:
        """Commit a new version of `<slug>/CLAUDE.md` if the remote is still
        at `expected_remote_sha`. Returns the new blob SHA.

        Raises OptimisticLockError if the remote advanced — caller must merge
        against the new head and retry.

        Commit attribution: author = dev (from JWT), committer = bot
        (from config). Preserves `git blame` correctness in the private repo.
        """
        headers = self._headers()
        path = f"{slug}/CLAUDE.md"

        async with httpx.AsyncClient(timeout=30, headers=headers) as http:
            # 1. Discover default branch.
            repo_resp = await http.get(f"{GITHUB_API}/repos/{self.repo}")
            if repo_resp.status_code >= 400:
                raise FetchError(f"repo metadata: {repo_resp.status_code}")
            default_branch = repo_resp.json()["default_branch"]

            # 2. Current ref SHA (parent commit).
            ref_resp = await http.get(
                f"{GITHUB_API}/repos/{self.repo}/git/ref/heads/{default_branch}"
            )
            if ref_resp.status_code >= 400:
                raise FetchError(f"get ref: {ref_resp.status_code}")
            parent_commit_sha = ref_resp.json()["object"]["sha"]

            # 3. Optimistic lock: current blob SHA must match expected.
            contents_resp = await http.get(
                f"{GITHUB_API}/repos/{self.repo}/contents/{path}"
            )
            if contents_resp.status_code == 404:
                raise NotFoundError(slug)
            if contents_resp.status_code >= 400:
                raise FetchError(f"contents: {contents_resp.status_code}")
            current_blob_sha = contents_resp.json()["sha"]
            if current_blob_sha != expected_remote_sha:
                raise OptimisticLockError(current_blob_sha)

            # 4. Create blob.
            blob_resp = await http.post(
                f"{GITHUB_API}/repos/{self.repo}/git/blobs",
                json={
                    "content": base64.b64encode(content.encode("utf-8")).decode(),
                    "encoding": "base64",
                },
            )
            if blob_resp.status_code >= 400:
                raise CommitError(f"create blob: {blob_resp.status_code}")
            new_blob_sha = blob_resp.json()["sha"]

            # 5. Fetch parent commit's tree SHA.
            parent_commit_resp = await http.get(
                f"{GITHUB_API}/repos/{self.repo}/git/commits/{parent_commit_sha}"
            )
            if parent_commit_resp.status_code >= 400:
                raise CommitError(f"get parent commit: {parent_commit_resp.status_code}")
            base_tree_sha = parent_commit_resp.json()["tree"]["sha"]

            # 6. Create tree with the new blob replacing the old one at `path`.
            tree_resp = await http.post(
                f"{GITHUB_API}/repos/{self.repo}/git/trees",
                json={
                    "base_tree": base_tree_sha,
                    "tree": [
                        {
                            "path": path,
                            "mode": "100644",
                            "type": "blob",
                            "sha": new_blob_sha,
                        }
                    ],
                },
            )
            if tree_resp.status_code >= 400:
                raise CommitError(f"create tree: {tree_resp.status_code}")
            new_tree_sha = tree_resp.json()["sha"]

            # 7. Create commit with author=dev, committer=bot.
            commit_resp = await http.post(
                f"{GITHUB_API}/repos/{self.repo}/git/commits",
                json={
                    "message": message,
                    "tree": new_tree_sha,
                    "parents": [parent_commit_sha],
                    "author": {"name": author_name, "email": author_email},
                    "committer": {
                        "name": self.committer_name,
                        "email": self.committer_email,
                    },
                },
            )
            if commit_resp.status_code >= 400:
                raise CommitError(f"create commit: {commit_resp.status_code}")
            new_commit_sha = commit_resp.json()["sha"]

            # 8. Update ref (fast-forward).
            update_ref_resp = await http.patch(
                f"{GITHUB_API}/repos/{self.repo}/git/refs/heads/{default_branch}",
                json={"sha": new_commit_sha, "force": False},
            )
            if update_ref_resp.status_code >= 400:
                raise CommitError(f"update ref: {update_ref_resp.status_code}")

        return new_blob_sha
