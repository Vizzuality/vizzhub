"""MCP data-layer helpers for DevStack project contexts.

Lightweight read/push helpers; tool-level logic (permissions, command queue,
JSON serialisation) is handled in `mcp_server/tools/devstack.py`.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.models.project import ProjectDB
from app.core.services.integration_token_service import IntegrationTokenService
from app.modules.devstack.models.project_context import DevstackProjectContextDB
from app.modules.devstack.services.project_context_github import (
    NotFoundError as GitHubNotFoundError,
    OptimisticLockError,
    ProjectContextGitHubClient,
)


class ContextNotFoundError(Exception):
    """Slug is not registered in VizzHub."""


class GitHubTokenMissingError(Exception):
    """No GitHub integration token configured in VizzHub."""


async def _require_github_token(session: AsyncSession) -> str:
    token = await IntegrationTokenService.get_token(session, "github")
    if not token:
        raise GitHubTokenMissingError(
            "GitHub integration token not configured — set it in VizzHub admin"
        )
    return token


def _build_github_client(token: str) -> ProjectContextGitHubClient:
    settings = get_settings()
    return ProjectContextGitHubClient(
        repo=settings.devstack_project_contexts_repo,
        token=token,
        committer_name=settings.devstack_project_contexts_committer_name,
        committer_email=settings.devstack_project_contexts_committer_email,
    )


async def list_contexts(session: AsyncSession) -> list[dict]:
    result = await session.execute(
        select(
            DevstackProjectContextDB.slug,
            DevstackProjectContextDB.description,
            ProjectDB.name,
        )
        .join(ProjectDB, DevstackProjectContextDB.project_id == ProjectDB.id)
        .order_by(DevstackProjectContextDB.slug)
    )
    return [
        {"slug": slug, "description": desc, "project_name": name}
        for slug, desc, name in result.all()
    ]


async def _get_or_raise(
    session: AsyncSession, slug: str
) -> DevstackProjectContextDB:
    result = await session.execute(
        select(DevstackProjectContextDB).where(
            DevstackProjectContextDB.slug == slug
        )
    )
    ctx = result.scalar_one_or_none()
    if ctx is None:
        raise ContextNotFoundError(slug)
    return ctx


async def get_context(
    session: AsyncSession, *, slug: str, at_sha: str | None
) -> dict:
    """Fetch remote CLAUDE.md content, either HEAD or a specific historical blob.

    Returns {target_path, content, devstack_sha, slug}.
    """
    await _get_or_raise(session, slug)
    token = await _require_github_token(session)
    client = _build_github_client(token)
    if at_sha is None:
        try:
            content, sha = await client.fetch_head(slug)
        except GitHubNotFoundError:
            raise ContextNotFoundError(f"{slug}/CLAUDE.md not found in repo")
    else:
        try:
            content = await client.fetch_at_sha(at_sha)
        except GitHubNotFoundError:
            raise ContextNotFoundError(f"blob {at_sha}")
        sha = at_sha
    return {
        "target_path": "CLAUDE.md",
        "content": content,
        "devstack_sha": sha,
        "slug": slug,
    }


async def push_context(
    session: AsyncSession,
    *,
    slug: str,
    content: str,
    expected_remote_sha: str,
    author_name: str,
    author_email: str,
) -> dict:
    """Publish new content. Returns one of three shapes:
      {status: "committed", new_sha}
      {status: "up_to_date", remote_sha}
      {status: "conflict", remote_sha}

    The caller is responsible for creating the auto-approved command-queue
    row (this helper does not touch the queue).
    """
    await _get_or_raise(session, slug)
    token = await _require_github_token(session)
    client = _build_github_client(token)

    try:
        current_content, current_sha = await client.fetch_head(slug)
    except GitHubNotFoundError:
        raise ContextNotFoundError(f"{slug}/CLAUDE.md not found in repo")

    if current_content == content:
        return {"status": "up_to_date", "remote_sha": current_sha}

    if current_sha != expected_remote_sha:
        return {"status": "conflict", "remote_sha": current_sha}

    message = f"Update {slug}/CLAUDE.md via VizzHub ({author_email})"
    try:
        new_sha = await client.push(
            slug=slug,
            content=content,
            expected_remote_sha=expected_remote_sha,
            author_name=author_name,
            author_email=author_email,
            message=message,
        )
    except OptimisticLockError as exc:
        return {"status": "conflict", "remote_sha": exc.current_sha}

    return {"status": "committed", "new_sha": new_sha}
