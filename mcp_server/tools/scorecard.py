"""Scorecard MCP tools — registered on the FastMCP server."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from mcp.server.fastmcp import FastMCP

from mcp_server.data.base import get_read_session
from mcp_server.data import scorecard as scorecard_data
from mcp_server.auth.permissions import mcp_requires


def _to_json(data: Any) -> str:
    """Serialize data to indented JSON with safe date/uuid handling."""
    return json.dumps(data, indent=2, default=str)


@mcp_requires("scorecard:view")
async def scorecard_get_project_scores(status: str | None = None) -> str:
    """List all scored projects with their latest overall score and dimension breakdown.

    Returns a JSON array of projects. Each entry includes the project name,
    overall score (0-100), and scores for 8 dimensions: time, cost, quality,
    value, satisfaction, flow, engineering, risk. Projects without metrics
    have null scores.

    Args:
        status: Filter by project status (proposal, live, finished).
    """
    async with get_read_session() as session:
        projects = await scorecard_data.get_project_scores(session, status=status)
    return _to_json(projects)


@mcp_requires("scorecard:view")
async def scorecard_get_project_scorecard(
    project_id: str,
    year: int | None = None,
    month: int | None = None,
) -> str:
    """Get the full scorecard for a single project.

    Returns JSON with the overall score, 8 dimension scores (0-100),
    normalized indicators (0-1), DORA metrics classification, EVM data
    (budget, cost, completion), and milestones. Defaults to latest
    period; specify year and month for historical data.

    Args:
        project_id: Project UUID (from scorecard_get_project_scores).
        year: Period year (e.g. 2026). Required with month.
        month: Period month (1-12). Required with year.
    """
    try:
        pid = UUID(project_id)
    except ValueError:
        return _to_json({"error": f"Invalid project_id: {project_id}"})

    async with get_read_session() as session:
        result = await scorecard_data.get_project_scorecard(
            session, pid, year=year, month=month,
        )

    if result is None:
        return _to_json({"error": f"Project '{project_id}' not found"})
    return _to_json(result)


@mcp_requires("scorecard:view")
async def scorecard_get_project_history(
    project_id: str,
    limit: int = 12,
) -> str:
    """Get score trend for a project over recent periods.

    Returns a JSON array of periods (newest first), each with overall
    score, dimension scores, and key indicators (SPI, CPI, lead time,
    etc.). Useful for spotting trends and deterioration patterns.

    Args:
        project_id: Project UUID (from scorecard_get_project_scores).
        limit: Max periods to return (default 12, max 48).
    """
    try:
        pid = UUID(project_id)
    except ValueError:
        return _to_json({"error": f"Invalid project_id: {project_id}"})

    effective_limit = min(max(limit, 1), 48)

    async with get_read_session() as session:
        result = await scorecard_data.get_project_history(
            session, pid, limit=effective_limit,
        )

    if result is None:
        return _to_json({"error": f"Project '{project_id}' not found"})
    return _to_json(result)


@mcp_requires("scorecard:view")
async def scorecard_get_global_metrics(limit: int = 12) -> str:
    """Get organization-wide averaged scores and indicators by month.

    Returns a JSON array of monthly records (newest first). Each record
    includes averaged dimension scores (0-100) and key indicators (0-1)
    across all projects, plus the count of contributing projects. Useful
    for benchmarking individual projects against the organization average.

    Args:
        limit: Max months to return (default 12, max 48).
    """
    effective_limit = min(max(limit, 1), 48)

    async with get_read_session() as session:
        records = await scorecard_data.get_global_metrics(
            session, limit=effective_limit,
        )
    return _to_json(records)


def register_scorecard_tools(server: FastMCP) -> None:
    """Register all Scorecard tools on the given MCP server instance."""
    server.tool()(scorecard_get_project_scores)
    server.tool()(scorecard_get_project_scorecard)
    server.tool()(scorecard_get_project_history)
    server.tool()(scorecard_get_global_metrics)
