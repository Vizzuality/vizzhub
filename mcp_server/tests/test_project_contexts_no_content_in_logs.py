"""Integration test: private CLAUDE.md content must never appear in logs.

Drives the two MCP tools (get, update) through the MCP layer with mocked
GitHub responses containing a distinctive canary string and asserts the
canary does not appear in captured structlog output.
"""

import base64
import pytest
import pytest_asyncio
import respx
import httpx
from unittest.mock import AsyncMock, MagicMock, patch
from structlog.testing import capture_logs

from mcp_server.tools.devstack import (
    devstack_get_project_context,
    devstack_update_project_context,
)
from mcp_server.data.base import McpUserContext, _mcp_user_context, override_session

CANARY = "CANARY_PRIVATE_TEXT_9f7e3a1b2c4d"

_MCP_USER = McpUserContext(
    user_id="00000000-0000-0000-0000-000000000042",
    email="dev@vizzuality.com",
    roles=["user"],
    permissions=["devstack:view"],
)


@pytest.fixture(autouse=True)
def set_user():
    token = _mcp_user_context.set(_MCP_USER)
    yield
    _mcp_user_context.reset(token)


@pytest_asyncio.fixture
async def linked_context(db_session):
    """Insert a project + context row so the data layer finds the slug."""
    from app.core.models.project import ProjectDB
    from app.modules.devstack.models.project_context import DevstackProjectContextDB

    project = ProjectDB(name="Acme")
    db_session.add(project)
    await db_session.flush()

    ctx = DevstackProjectContextDB(
        slug="acme-corp",
        project_id=project.id,
        description=None,
    )
    db_session.add(ctx)
    await db_session.flush()
    await db_session.commit()
    return ctx


@respx.mock
@pytest.mark.asyncio
async def test_get_does_not_log_content(db_session, linked_context):
    """Fetched CLAUDE.md content must not appear in any structlog event."""
    respx.get(
        "https://api.github.com/repos/Vizzuality/project-contexts"
        "/contents/acme-corp/CLAUDE.md"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "sha": "blob-1",
                "content": base64.b64encode(CANARY.encode()).decode(),
                "encoding": "base64",
            },
        )
    )

    # Monkeypatch token lookup so no real GitHub token row is needed in the DB.
    with patch(
        "mcp_server.data.project_contexts._require_github_token",
        new=AsyncMock(return_value="fake-token"),
    ):
        async with override_session(db_session):
            with capture_logs() as logs:
                await devstack_get_project_context(slug="acme-corp")

    serialised = repr(logs)
    assert CANARY not in serialised, (
        "Private CLAUDE.md content leaked into structlog output during get"
    )


@respx.mock
@pytest.mark.asyncio
async def test_update_does_not_log_content(db_session, linked_context):
    """Content passed to update must not appear in any structlog event."""
    respx.get(
        "https://api.github.com/repos/Vizzuality/project-contexts"
    ).mock(return_value=httpx.Response(200, json={"default_branch": "main"}))
    respx.get(
        "https://api.github.com/repos/Vizzuality/project-contexts"
        "/git/ref/heads/main"
    ).mock(return_value=httpx.Response(200, json={"object": {"sha": "c1"}}))
    respx.get(
        "https://api.github.com/repos/Vizzuality/project-contexts"
        "/contents/acme-corp/CLAUDE.md"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "sha": "expected",
                "content": base64.b64encode(b"old").decode(),
                "encoding": "base64",
            },
        )
    )
    respx.post(
        "https://api.github.com/repos/Vizzuality/project-contexts/git/blobs"
    ).mock(return_value=httpx.Response(201, json={"sha": "new-blob"}))
    respx.get(
        "https://api.github.com/repos/Vizzuality/project-contexts"
        "/git/commits/c1"
    ).mock(return_value=httpx.Response(200, json={"tree": {"sha": "t1"}}))
    respx.post(
        "https://api.github.com/repos/Vizzuality/project-contexts/git/trees"
    ).mock(return_value=httpx.Response(201, json={"sha": "new-tree"}))
    respx.post(
        "https://api.github.com/repos/Vizzuality/project-contexts/git/commits"
    ).mock(return_value=httpx.Response(201, json={"sha": "c2"}))
    respx.patch(
        "https://api.github.com/repos/Vizzuality/project-contexts"
        "/git/refs/heads/main"
    ).mock(return_value=httpx.Response(200, json={"object": {"sha": "c2"}}))

    fake_cmd = MagicMock()
    fake_cmd.id = "00000000-0000-0000-0000-000000000099"

    with (
        patch(
            "mcp_server.data.project_contexts._require_github_token",
            new=AsyncMock(return_value="fake-token"),
        ),
        # CommandService.enqueue_approved inserts a row with a FK to users.id;
        # the fake user UUID is not in the test DB, so we stub the whole call.
        patch(
            "mcp_server.tools.devstack.CommandService.enqueue_approved",
            new=AsyncMock(return_value=fake_cmd),
        ),
        # session.get(UserDB, ...) returns None for unknown UUIDs; the tool
        # handles that gracefully by falling back to user.email.
    ):
        async with override_session(db_session):
            with capture_logs() as logs:
                await devstack_update_project_context(
                    slug="acme-corp",
                    content=CANARY,
                    expected_remote_sha="expected",
                )

    serialised = repr(logs)
    assert CANARY not in serialised, (
        "Canary content string leaked into structlog output during push"
    )
