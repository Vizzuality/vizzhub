"""Events MCP tools — registered on the FastMCP server."""

from __future__ import annotations

from typing import Annotated, Literal

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from app.core.permissions import Action
from mcp_server.auth.permissions import mcp_requires
from mcp_server.data import events as events_data
from mcp_server.data.base import get_read_session
from mcp_server.tools._annotations import READ_ONLY
from mcp_server.tools._shared import to_json

AttendingLiteral = Literal["yes", "no", "maybe", "attended"]
Year = Annotated[int, Field(ge=2000, le=2100)]


@mcp_requires(Action.EVENTS_VIEW)
async def events_list(
    year: Year | None = None,
    quarter: Annotated[int, Field(ge=1, le=4)] | None = None,
    attending: AttendingLiteral | None = None,
    theme: str | None = None,
    event_type: str | None = None,
    region: str | None = None,
    search: str | None = None,
    limit: Annotated[int, Field(ge=1, le=200)] = 100,
) -> str:
    """List conferences and events Vizzuality tracks, with who goes and what it costs.

    Returns JSON `{events, total, returned}` ordered by start date. Each
    event has name, type, primary/secondary theme, region focus, city,
    country, start/end date, attending decision, rating (1-5), other_costs,
    total_cost (other_costs + every attendee's cost), attendees (user_id,
    name, functional_area, role, cost) and the app URL. Costs are in EUR.

    Args:
        year: Calendar year of the start date.
        quarter: Quarter (1-4) of the start date.
        attending: "yes", "no", "maybe" (includes undecided) or "attended"
            (yes and already ended).
        theme: Primary theme, exact (e.g. "Climate", "Nature & Biodiversity").
        event_type: Exact type (e.g. "Conference", "Webinar").
        region: Region focus, exact (e.g. "Europe", "Global").
        search: Case-insensitive substring of the event name.
        limit: Max events returned (default 100, max 200); `total` tells
            whether more matched.
    """
    async with get_read_session() as session:
        result = await events_data.list_events(
            session,
            year=year,
            quarter=quarter,
            attending=attending,
            theme=theme,
            event_type=event_type,
            region=region,
            search=search,
            limit=limit,
        )
    return to_json(result)


@mcp_requires(Action.EVENTS_VIEW)
async def events_get_stats(
    year: Year | None = None,
    attending: AttendingLiteral | None = None,
) -> str:
    """Get the events dashboard aggregates.

    Returns JSON with total_events, total_attendees (distinct people),
    total_cost (EUR) and `{label, count}` breakdowns: by_quarter, by_theme,
    by_type, by_region, by_country (events) and by_role, by_fa
    (attendances, one per person per event).

    Args:
        year: Calendar year of the start date.
        attending: "yes", "no", "maybe" (includes undecided) or "attended"
            (yes and already ended).
    """
    async with get_read_session() as session:
        result = await events_data.get_stats(session, year=year, attending=attending)
    return to_json(result)


def register_events_tools(server: FastMCP) -> None:
    """Register all Events tools on the given MCP server instance."""
    server.tool(annotations=READ_ONLY)(events_list)
    server.tool(annotations=READ_ONLY)(events_get_stats)
