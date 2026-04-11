"""MCP server definition — registers tools from each module."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

_INSTRUCTIONS = (
    "VizzHub is Vizzuality's internal operations hub. "
    "Use the ISO tools to query compliance registries and documents. "
    "Registry slugs are listed by iso_get_registries. "
    "Document content can be searched with iso_search_documents."
)


def create_mcp_server(
    auth_server_provider=None,
    token_verifier=None,
    auth_settings=None,
    http_mode: bool = False,
) -> FastMCP:
    """Create the MCP server instance.

    Without auth params: returns a server for stdio transport (Phase 1 behavior).
    With auth params + http_mode: returns a server configured for HTTP transport
    with OAuth. http_mode sets streamable_http_path="/" to avoid /mcp/mcp path
    doubling when mounted as sub-app at /mcp on FastAPI.

    Note: tool registration happens at module import time via the module-level
    `mcp` instance. Callers using this factory for HTTP mode must ensure tools
    are registered separately (import mcp_server.tools.iso after creation).
    """
    kwargs = {}
    if http_mode:
        kwargs["streamable_http_path"] = "/"

    instance = FastMCP(
        "VizzHub",
        instructions=_INSTRUCTIONS,
        auth_server_provider=auth_server_provider,
        token_verifier=token_verifier,
        auth=auth_settings,
        **kwargs,
    )

    return instance


# Default instance for stdio (backward compatible).
# Tools are registered on this instance by importing mcp_server.tools.iso below.
mcp = create_mcp_server()

import mcp_server.tools.iso  # noqa: F401, E402 — registers tools on mcp
