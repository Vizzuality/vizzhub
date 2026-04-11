"""MCP server definition — registers tools from each module."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

_INSTRUCTIONS = (
    "VizzHub is Vizzuality's internal operations hub. "
    "Use the ISO tools to query compliance registries and documents. "
    "Registry slugs are listed by iso_get_registries. "
    "Document content can be searched with iso_search_documents. "
    "Use the Tracker tools to query project budgets, time allocation, "
    "invoices, and progress. Start with tracker_get_projects to list "
    "projects, then drill into detail, time, invoices, or progress. "
    "Use the Scorecard tools to query project health scores across 8 "
    "dimensions. Start with scorecard_get_project_scores for an overview, "
    "then drill into individual scorecards or score history."
)


def create_mcp_server(
    auth_server_provider=None,
    token_verifier=None,
    auth_settings=None,
    http_mode: bool = False,
    allowed_hosts: list[str] | None = None,
) -> FastMCP:
    """Create the MCP server instance with all tools registered.

    Without auth params: returns a server for stdio transport (Phase 1 behavior).
    With auth params + http_mode: returns a server configured for HTTP transport
    with OAuth. http_mode sets streamable_http_path="/" to avoid /mcp/mcp path
    doubling when mounted as sub-app at /mcp on FastAPI.
    """
    from mcp.server.transport_security import TransportSecuritySettings

    kwargs: dict = {}
    if http_mode:
        # SSE transport: GET /sse (stream), POST /messages/ (client messages)
        # Defaults: sse_path="/sse", message_path="/messages/"
        # Behind ALB the Host header is the public domain, not localhost.
        kwargs["transport_security"] = TransportSecuritySettings(
            enable_dns_rebinding_protection=bool(allowed_hosts),
            allowed_hosts=allowed_hosts or [],
        )

    instance = FastMCP(
        "VizzHub",
        instructions=_INSTRUCTIONS,
        auth_server_provider=auth_server_provider,
        token_verifier=token_verifier,
        auth=auth_settings,
        **kwargs,
    )

    from mcp_server.tools.iso import register_iso_tools  # noqa: PLC0415
    register_iso_tools(instance)

    from mcp_server.tools.tracker import register_tracker_tools  # noqa: PLC0415
    register_tracker_tools(instance)

    from mcp_server.tools.scorecard import register_scorecard_tools  # noqa: PLC0415
    register_scorecard_tools(instance)

    return instance


# Default instance for stdio (backward compatible).
mcp = create_mcp_server()
