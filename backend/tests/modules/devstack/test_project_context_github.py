"""Tests for ProjectContextGitHubClient."""

import base64
import pytest
import respx
import httpx

from app.modules.devstack.services.project_context_github import (
    ProjectContextGitHubClient,
    NotFoundError,
    NoContentError,
)


@pytest.fixture
def client():
    return ProjectContextGitHubClient(
        repo="Vizzuality/project-contexts",
        token="fake-token",
        committer_name="VizzHub Bot",
        committer_email="bot@vizzuality.com",
    )


@respx.mock
@pytest.mark.asyncio
async def test_fetch_head_returns_content_and_sha(client):
    respx.get(
        "https://api.github.com/repos/Vizzuality/project-contexts/contents/acme-corp/CLAUDE.md"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "sha": "abc123",
                "content": base64.b64encode(b"# Acme").decode(),
                "encoding": "base64",
            },
        )
    )
    content, sha = await client.fetch_head("acme-corp")
    assert content == "# Acme"
    assert sha == "abc123"


@respx.mock
@pytest.mark.asyncio
async def test_fetch_head_404(client):
    respx.get(
        "https://api.github.com/repos/Vizzuality/project-contexts/contents/missing/CLAUDE.md"
    ).mock(return_value=httpx.Response(404))
    with pytest.raises(NotFoundError):
        await client.fetch_head("missing")


@respx.mock
@pytest.mark.asyncio
async def test_fetch_at_sha_returns_historical_blob(client):
    respx.get(
        "https://api.github.com/repos/Vizzuality/project-contexts/git/blobs/oldsha"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "sha": "oldsha",
                "content": base64.b64encode(b"# Old Acme").decode(),
                "encoding": "base64",
            },
        )
    )
    content = await client.fetch_at_sha("oldsha")
    assert content == "# Old Acme"


@respx.mock
@pytest.mark.asyncio
async def test_fetch_at_sha_404(client):
    respx.get(
        "https://api.github.com/repos/Vizzuality/project-contexts/git/blobs/nope"
    ).mock(return_value=httpx.Response(404))
    with pytest.raises(NotFoundError):
        await client.fetch_at_sha("nope")
