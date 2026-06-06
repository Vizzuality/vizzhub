"""Streamable HTTP transport wiring tests.

Mirrors the mount wiring from `app/main.py` in isolation (no DB) to lock in the
SSE→Streamable HTTP cutover (2026-06-06):
  - the streamable endpoint mounts at the canonical /mcp/ and enforces OAuth
    (401 + WWW-Authenticate), so an unauthenticated client cannot reach tools;
  - /mcp without the trailing slash 404s (MCP SDK behaviour);
  - the session manager's task group starts and stops cleanly from a FastAPI
    lifespan (FastAPI does not propagate a mounted sub-app's lifespan);
  - the retired SSE endpoints (/mcp/sse, /mcp/messages/) are gone.

These are pure-ASGI tests: the provider is constructed but its DB-backed flows
are never exercised, so no test database is required.
"""

from __future__ import annotations

from contextlib import asynccontextmanager

import httpx
import pytest
from fastapi import FastAPI
from mcp.server.auth.settings import (
    AuthSettings,
    ClientRegistrationOptions,
    RevocationOptions,
)
from starlette.responses import PlainTextResponse
from starlette.routing import Mount, Route

from mcp_server.auth.provider import VizzHubOAuthProvider
from mcp_server.server import create_mcp_server

BASE_URL = "https://hub.vizzuality.com/mcp"
HOST = "hub.vizzuality.com"


def _build_app() -> tuple[FastAPI, object]:
    """Build a FastAPI app with Streamable HTTP mounted at /mcp.

    Replicates the mount/lifespan logic of `app/main.py` (the production wiring)
    without its DB-dependent startup steps.
    """
    provider = VizzHubOAuthProvider(
        session_maker=None,
        jwt_secret="test-secret",
        google_client_id="test-client",
        allowed_google_domain="vizzuality.com",
        base_url=BASE_URL,
    )
    auth_settings = AuthSettings(
        issuer_url=BASE_URL,
        resource_server_url=BASE_URL,
        client_registration_options=ClientRegistrationOptions(
            enabled=True, valid_scopes=["read"], default_scopes=["read"]
        ),
        revocation_options=RevocationOptions(enabled=True),
        required_scopes=["read"],
    )
    mcp_server = create_mcp_server(
        auth_server_provider=provider,
        auth_settings=auth_settings,
        http_mode=True,
        allowed_hosts=[HOST],
    )

    async def _callback(request):  # noqa: ANN001
        return PlainTextResponse("ok")

    streamable = mcp_server.streamable_http_app()
    session_manager = mcp_server.session_manager
    streamable.routes.append(
        Route("/oauth/callback", endpoint=_callback, methods=["GET"])
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        async with session_manager.run():
            yield

    app = FastAPI(lifespan=lifespan, redirect_slashes=False)
    app.mount("/mcp", streamable)
    return app, session_manager


def _client(app: FastAPI) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url=f"https://{HOST}"
    )


def test_streamable_mounts_at_canonical_mcp() -> None:
    """The single endpoint is served at the /mcp mount root (streamable_http_path='/')."""
    app, _ = _build_app()
    mounts = {r.path: r for r in app.routes if isinstance(r, Mount)}
    assert "/mcp" in mounts

    paths = {getattr(x, "path", None) for x in mounts["/mcp"].app.routes}
    assert "/" in paths
    # The deprecated SSE endpoints are gone.
    assert "/sse" not in paths
    assert "/messages" not in paths


@pytest.mark.asyncio
async def test_streamable_requires_auth() -> None:
    """An unauthenticated POST to /mcp/ is rejected with 401 + WWW-Authenticate."""
    app, _ = _build_app()
    async with app.router.lifespan_context(app):
        async with _client(app) as client:
            resp = await client.post(
                "/mcp/",
                json={"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}},
                headers={"Accept": "application/json, text/event-stream"},
            )
    assert resp.status_code == 401
    assert resp.headers.get("www-authenticate", "").startswith("Bearer")


@pytest.mark.asyncio
async def test_streamable_endpoint_needs_trailing_slash() -> None:
    """/mcp without the trailing slash is not the endpoint (SDK behaviour)."""
    app, _ = _build_app()
    async with app.router.lifespan_context(app):
        async with _client(app) as client:
            resp = await client.post("/mcp", json={})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_legacy_sse_endpoint_removed() -> None:
    """The retired SSE message endpoint no longer exists."""
    app, _ = _build_app()
    async with app.router.lifespan_context(app):
        async with _client(app) as client:
            resp = await client.post("/mcp/messages/", json={})
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_session_manager_runs_from_lifespan() -> None:
    """The session manager task group starts and stops cleanly via the lifespan."""
    app, manager = _build_app()
    async with app.router.lifespan_context(app):
        # Inside the context the manager's task group is live; a request reaches
        # the transport layer (rejected for auth, but routed — not a 500/404).
        async with _client(app) as client:
            resp = await client.get("/mcp/", headers={"Accept": "text/event-stream"})
        assert resp.status_code == 401
    # Exiting the context tears the task group down without raising.
    assert type(manager).__name__ == "StreamableHTTPSessionManager"
