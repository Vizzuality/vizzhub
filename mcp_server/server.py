"""MCP server definition — registers tools from each module."""

from __future__ import annotations

from pathlib import Path

from mcp.server.fastmcp import FastMCP

_SKILL_PATH = Path(__file__).resolve().parent.parent / "docs" / "mcp" / "vizzhub-skill.md"
_SKILL_CONTENT = _SKILL_PATH.read_text(encoding="utf-8") if _SKILL_PATH.exists() else ""

_INSTRUCTIONS = """\
**CRITICAL — HUMAN-IN-THE-LOOP FOR WRITES:** Write tools (iso_*, playbook_*, portfolio_*)
NEVER execute directly — they only queue a command and return a summary.
`approve_command` and `approve_all` are NOT shortcuts for the assistant to
complete its task. They MUST ONLY be called AFTER the human user has seen
the summary in chat and explicitly confirmed (e.g. "ok", "approve", "sí",
"yes"). Do NOT call approve_* in the same turn as the write tool. Do NOT
auto-approve to "be helpful". Do NOT loop approve_all on your own. If the
user has not clearly confirmed, stop and ask. Auto-approving defeats the
whole purpose of the queue.

VizzHub is Vizzuality's internal operations hub with 8 modules:

| Module | Key ID | Tools prefix |
|--------|--------|-------------|
| Users | user_id (UUID) | users_ |
| Tracker | project_id (UUID) | tracker_ |
| Scorecard | project_id (UUID) | scorecard_ |
| Capacity | user_id + period (YYYY-MM) | capacity_ |
| Portfolio | program_id (UUID) | portfolio_ |
| ISO | slug (string) | iso_ |
| Playbook | slug (string) | playbook_ |
| DevStack | name (string) | devstack_ |

Key joins: user_id is the same UUID across Users, Capacity, and Tracker. \
project_id is the same UUID across Tracker and Scorecard. A Portfolio program \
groups project iterations — the project_id of each iteration is the same UUID \
used by Tracker and Scorecard.

FA mapping (Capacity short codes → Users full names): \
FE=Frontend Developer, BE=Backend Developer, Design=Designer, \
PM=Project Manager, Sci=Scientist, Coms=Communications.

App URLs (base: https://hub.vizzuality.com):
- Project scorecard: /scorecard/{project_id}
- Tracker project: /tracker/projects/{project_id}
- Invoice detail: /tracker/invoices/{invoice_id}
- Capacity insights: /capacity/insights (add ?fa=FE to filter)
- ISO document: /iso/docs?page={slug}
- Playbook article: /playbook?page={slug}
- Portfolio program: /portfolio/programs/{program_id}
- Admin user: /admin/users/{user_id}
Always include full URLs in responses using IDs/slugs from tool results.

Conventions:
- Null scores mean no data, not zero.
- Cost values are currency-specific — check the currency field.
- burn_percentage is null when budget is zero.
- Invoice status is the effective status (accounts for postponements).
- Capacity percentages are 0-100 scale.
- iso_search_documents uses full-text search; iso_get_documents(search=) is title-only.
- Yearly registries follow the ISO audit cycle, not the calendar year. Each cycle \
runs approximately March to February. The year parameter refers to the cycle start \
year: year=2025 covers the 2025-2026 cycle (roughly March 2025 - February 2026). \
When the user says "this period" or "current cycle", use the cycle that includes \
today's date.

For cross-module query patterns, detailed tool reference, and registry lists, \
read the vizzhub://data-model resource before planning complex queries.\
"""


def create_mcp_server(
    auth_server_provider=None,
    token_verifier=None,
    auth_settings=None,
    http_mode: bool = False,
    allowed_hosts: list[str] | None = None,
) -> FastMCP:
    """Create the MCP server instance with all tools registered.

    Without auth params: returns a server for stdio transport (Phase 1 behavior).
    With auth params + http_mode: returns a server configured for Streamable HTTP
    transport with OAuth, mounted as a sub-app at /mcp on FastAPI.
    """
    from mcp.server.transport_security import TransportSecuritySettings

    kwargs: dict = {}
    if http_mode:
        # Streamable HTTP: a single endpoint at streamable_http_path.
        # streamable_http_path="/" so that mounting the sub-app at /mcp yields
        # the canonical endpoint /mcp/ (the default "/mcp" would double to
        # /mcp/mcp). Behind the ALB the Host header is the public domain, not
        # localhost — hence the transport_security allowed_hosts below.
        kwargs["streamable_http_path"] = "/"
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

    from mcp_server.tools.capacity import register_capacity_tools  # noqa: PLC0415
    register_capacity_tools(instance)

    from mcp_server.tools.playbook import register_playbook_tools  # noqa: PLC0415
    register_playbook_tools(instance)

    from mcp_server.tools.users import register_users_tools  # noqa: PLC0415
    register_users_tools(instance)

    from mcp_server.tools.portfolio import register_portfolio_tools  # noqa: PLC0415
    register_portfolio_tools(instance)

    from mcp_server.tools.iso_write import register_iso_write_tools  # noqa: PLC0415
    register_iso_write_tools(instance)

    from mcp_server.tools.playbook_write import register_playbook_write_tools  # noqa: PLC0415
    register_playbook_write_tools(instance)

    from mcp_server.tools.portfolio_write import register_portfolio_write_tools  # noqa: PLC0415
    register_portfolio_write_tools(instance)

    from mcp_server.tools.commands import register_command_tools  # noqa: PLC0415
    register_command_tools(instance)

    from mcp_server.tools.devstack import register_devstack_tools  # noqa: PLC0415
    register_devstack_tools(instance)

    if _SKILL_CONTENT:

        @instance.resource(
            "vizzhub://data-model",
            name="VizzHub Data Model Guide",
            description=(
                "Complete reference for every VizzHub module (Users, Tracker, "
                "Scorecard, Capacity, ISO, Portfolio, Playbook): data models, "
                "read tools, cross-module query patterns, registry lists "
                "(yearly vs non-yearly), and URL construction. Read this "
                "before planning multi-tool queries."
            ),
            mime_type="text/markdown",
        )
        def get_data_model() -> str:
            return _SKILL_CONTENT

    return instance


# Default instance for stdio (backward compatible).
mcp = create_mcp_server()
