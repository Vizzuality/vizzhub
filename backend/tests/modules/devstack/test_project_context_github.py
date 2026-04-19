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


@respx.mock
@pytest.mark.asyncio
async def test_push_success_returns_new_sha(client):
    # 1. get default branch head
    respx.get(
        "https://api.github.com/repos/Vizzuality/project-contexts"
    ).mock(return_value=httpx.Response(200, json={"default_branch": "main"}))
    respx.get(
        "https://api.github.com/repos/Vizzuality/project-contexts/git/ref/heads/main"
    ).mock(return_value=httpx.Response(200, json={"object": {"sha": "commit-sha-1"}}))
    # 2. verify current blob SHA matches expected
    respx.get(
        "https://api.github.com/repos/Vizzuality/project-contexts/contents/acme-corp/CLAUDE.md"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "sha": "expected-blob-sha",
                "content": base64.b64encode(b"old").decode(),
                "encoding": "base64",
            },
        )
    )
    # 3. create blob
    respx.post(
        "https://api.github.com/repos/Vizzuality/project-contexts/git/blobs"
    ).mock(return_value=httpx.Response(201, json={"sha": "new-blob-sha"}))
    # 4. get base commit to extract its tree
    respx.get(
        "https://api.github.com/repos/Vizzuality/project-contexts/git/commits/commit-sha-1"
    ).mock(return_value=httpx.Response(200, json={"tree": {"sha": "base-tree-sha"}}))
    # 5. create tree
    respx.post(
        "https://api.github.com/repos/Vizzuality/project-contexts/git/trees"
    ).mock(return_value=httpx.Response(201, json={"sha": "new-tree-sha"}))
    # 6. create commit
    respx.post(
        "https://api.github.com/repos/Vizzuality/project-contexts/git/commits"
    ).mock(return_value=httpx.Response(201, json={"sha": "commit-sha-2"}))
    # 7. update ref
    respx.patch(
        "https://api.github.com/repos/Vizzuality/project-contexts/git/refs/heads/main"
    ).mock(return_value=httpx.Response(200, json={"object": {"sha": "commit-sha-2"}}))

    new_sha = await client.push(
        slug="acme-corp",
        content="new content",
        expected_remote_sha="expected-blob-sha",
        author_name="Miguel",
        author_email="miguel@vizzuality.com",
        message="Update acme-corp/CLAUDE.md via VizzHub (miguel@vizzuality.com)",
    )
    assert new_sha == "new-blob-sha"


@respx.mock
@pytest.mark.asyncio
async def test_push_optimistic_lock_fails_when_remote_advanced(client):
    respx.get(
        "https://api.github.com/repos/Vizzuality/project-contexts"
    ).mock(return_value=httpx.Response(200, json={"default_branch": "main"}))
    respx.get(
        "https://api.github.com/repos/Vizzuality/project-contexts/git/ref/heads/main"
    ).mock(return_value=httpx.Response(200, json={"object": {"sha": "commit-sha-1"}}))
    respx.get(
        "https://api.github.com/repos/Vizzuality/project-contexts/contents/acme-corp/CLAUDE.md"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "sha": "actually-newer-sha",  # remote advanced
                "content": base64.b64encode(b"x").decode(),
                "encoding": "base64",
            },
        )
    )
    from app.modules.devstack.services.project_context_github import OptimisticLockError
    with pytest.raises(OptimisticLockError) as excinfo:
        await client.push(
            slug="acme-corp",
            content="new",
            expected_remote_sha="expected-blob-sha",
            author_name="Miguel",
            author_email="miguel@vizzuality.com",
            message="msg",
        )
    assert excinfo.value.current_sha == "actually-newer-sha"
