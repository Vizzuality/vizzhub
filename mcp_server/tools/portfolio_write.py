"""Portfolio write MCP tools — queue commands for human approval before execution."""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from app.core.permissions import Action
from mcp_server.auth.permissions import mcp_requires
from mcp_server.tools._annotations import WRITE
from mcp_server.tools._shared import enqueue_command


@mcp_requires(Action.PORTFOLIO_MANAGE)
async def portfolio_create_program(name: str) -> str:
    """Create a new program in the portfolio catalogue.

    This does NOT execute immediately. The command is queued for human
    approval. Use approve_command() with the returned command_id to
    execute, or reject_command() to discard.

    Args:
        name: Program name (must be unique, case-insensitive).

    Returns JSON with status, command_id, human-readable summary, and
    instructions for approval.
    """
    return await enqueue_command(
        "portfolio", "create_program",
        target=None,
        payload={"name": name},
    )


@mcp_requires(Action.PORTFOLIO_MANAGE)
async def portfolio_rename_program(program_id: str, name: str) -> str:
    """Rename an existing program.

    This does NOT execute immediately. The command is queued for human
    approval. Use approve_command() to execute.

    Args:
        program_id: Program UUID (from portfolio_search_programs or
            portfolio_list_programs).
        name: New program name.

    Returns JSON with status, command_id, summary, and approval instructions.
    """
    return await enqueue_command(
        "portfolio", "rename_program",
        target=program_id,
        payload={"name": name},
    )


@mcp_requires(Action.PORTFOLIO_MANAGE)
async def portfolio_update_profile(
    program_id: str,
    objective: str | None = None,
    short_description: str | None = None,
    impact_story: str | None = None,
    web_copy: str | None = None,
    website_url: str | None = None,
    main_partner: str | None = None,
    stage: str | None = None,
    on_website: bool | None = None,
) -> str:
    """Update narrative profile fields of a program (PATCH semantics).

    This does NOT execute immediately. The command is queued for human
    approval. Only the fields you pass are changed; omitted fields are
    left untouched. Pass an empty string ("") to clear a text field.
    Creates the profile if the program does not have one yet.

    Args:
        program_id: Program UUID.
        objective: What the program aims to achieve.
        short_description: One-paragraph description.
        impact_story: Narrative of achieved impact.
        web_copy: Marketing copy reference.
        website_url: Public website URL (http/https).
        stage: Lifecycle stage (see portfolio_get_taxonomies for the
            values in use, e.g. "live").
        main_partner: Main partner organisation.
        on_website: Whether the program is published on the public website.

    Returns JSON with status, command_id, summary, and approval instructions.
    """
    fields = {
        "objective": objective,
        "short_description": short_description,
        "impact_story": impact_story,
        "web_copy": web_copy,
        "website_url": website_url,
        "main_partner": main_partner,
        "stage": stage,
        "on_website": on_website,
    }
    payload = {key: value for key, value in fields.items() if value is not None}
    return await enqueue_command(
        "portfolio", "update_profile",
        target=program_id,
        payload=payload,
    )


@mcp_requires(Action.PORTFOLIO_MANAGE)
async def portfolio_set_tags(
    program_id: str,
    taxonomy: str,
    term_names: list[str],
    primary: str | None = None,
) -> str:
    """Replace a program's tags for ONE taxonomy.

    This does NOT execute immediately. The command is queued for human
    approval. The given terms REPLACE the program's current terms in that
    taxonomy (other taxonomies are untouched). Pass an empty list to clear
    the taxonomy's tags.

    Args:
        program_id: Program UUID.
        taxonomy: Taxonomy slug or name (from portfolio_get_taxonomies).
        term_names: Term names, case-insensitive (must exist and be active
            in the taxonomy). Single-cardinality taxonomies accept at most
            one term.
        primary: Term name to mark as primary (must be in term_names;
            only for taxonomies with allows_primary).

    Returns JSON with status, command_id, summary, and approval instructions.
    """
    payload: dict = {"taxonomy": taxonomy, "term_names": term_names}
    if primary is not None:
        payload["primary"] = primary
    return await enqueue_command(
        "portfolio", "set_tags",
        target=program_id,
        payload=payload,
    )


def register_portfolio_write_tools(server: FastMCP) -> None:
    """Register all Portfolio write tools on the given MCP server instance."""
    server.tool(annotations=WRITE)(portfolio_create_program)
    server.tool(annotations=WRITE)(portfolio_rename_program)
    server.tool(annotations=WRITE)(portfolio_update_profile)
    server.tool(annotations=WRITE)(portfolio_set_tags)
