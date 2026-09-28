"""Tool handlers must see the identity of the request that carried the call.

Streamable HTTP runs handlers in the session task, which inherits the
contextvars of the request that created the session. These tests drive a real
FastMCP streamable HTTP app with two tokens on one session.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from jose import jwt
from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings

from mcp_server.auth.token_verifier import VizzHubTokenVerifier
from mcp_server.data.base import get_mcp_user

SECRET = "test-secret-for-session-identity"
BASE_URL = "http://test"
ACCEPT = "application/json, text/event-stream"


def _token(sub: str, permissions: list[str]) -> str:
    return jwt.encode(
        {
            "sub": sub,
            "email": f"{sub}@vizzuality.com",
            "client_id": "client-1",
            "roles": ["user"],
            "permissions": permissions,
            "scopes": ["read"],
            "iss": "vizzhub",
            "aud": "vizzhub-mcp",
            "exp": datetime.now(timezone.utc) + timedelta(hours=1),
        },
        SECRET,
        algorithm="HS256",
    )


def _build_server() -> FastMCP:
    server = FastMCP(
        "identity-test",
        token_verifier=VizzHubTokenVerifier(secret_key=SECRET),
        auth=AuthSettings(
            issuer_url=BASE_URL,
            resource_server_url=BASE_URL,
            validate_token_resource=False,
            required_scopes=["read"],
        ),
        json_response=True,
        streamable_http_path="/",
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )

    @server.tool()
    async def whoami() -> str:
        user = get_mcp_user()
        return json.dumps({"sub": user.user_id, "permissions": user.permissions})

    return server


def _rpc(method: str, msg_id: int | None = None, params: dict | None = None) -> dict:
    body: dict = {"jsonrpc": "2.0", "method": method, "params": params or {}}
    if msg_id is not None:
        body["id"] = msg_id
    return body


async def _open_session(client: httpx.AsyncClient, token: str) -> str:
    headers = {"Authorization": f"Bearer {token}", "Accept": ACCEPT}
    init = await client.post(
        "/",
        headers=headers,
        json=_rpc("initialize", 1, {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "1"},
        }),
    )
    assert init.status_code == 200, init.text
    session_id = init.headers["mcp-session-id"]
    await client.post(
        "/",
        headers={**headers, "mcp-session-id": session_id},
        json=_rpc("notifications/initialized"),
    )
    return session_id


async def _call_whoami(client: httpx.AsyncClient, token: str, session_id: str) -> httpx.Response:
    return await client.post(
        "/",
        headers={"Authorization": f"Bearer {token}", "Accept": ACCEPT, "mcp-session-id": session_id},
        json=_rpc("tools/call", 2, {"name": "whoami", "arguments": {}}),
    )


@pytest.mark.asyncio
async def test_refreshed_token_permissions_apply_within_same_session() -> None:
    server = _build_server()
    app = server.streamable_http_app()
    first = _token("user-a", ["tracker:view"])
    refreshed = _token("user-a", ["tracker:view", "iso_docs:edit"])

    async with server.session_manager.run():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url=BASE_URL) as client:
            session_id = await _open_session(client, first)
            response = await _call_whoami(client, refreshed, session_id)

    assert response.status_code == 200, response.text
    identity = json.loads(response.json()["result"]["content"][0]["text"])
    assert identity == {"sub": "user-a", "permissions": ["tracker:view", "iso_docs:edit"]}


@pytest.mark.asyncio
async def test_other_user_cannot_reuse_session() -> None:
    server = _build_server()
    app = server.streamable_http_app()

    async with server.session_manager.run():
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url=BASE_URL) as client:
            session_id = await _open_session(client, _token("user-a", ["*"]))
            response = await _call_whoami(client, _token("user-b", []), session_id)

    assert response.status_code == 404
