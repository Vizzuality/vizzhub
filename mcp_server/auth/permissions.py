"""Permission enforcement for MCP tools."""

from __future__ import annotations

import functools

import structlog
from mcp.server.fastmcp.exceptions import ToolError

from mcp_server.data.base import get_mcp_user

logger = structlog.get_logger()


def mcp_requires(permission: str):
    """Decorator that gates an MCP tool behind a permission check.

    Raises ToolError on denial so FastMCP surfaces it as a tool-call error
    (distinguishable from a successful return value) and the LLM cannot
    silently re-route. Also emits a `mcp_permission_denied` structlog
    event for the audit trail.

    Uses functools.wraps to preserve function metadata for FastMCP
    schema introspection (inspect.signature follows __wrapped__).
    """
    def decorator(fn):
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            user = get_mcp_user()
            if not user.has_permission(permission):
                logger.warning(
                    "mcp_permission_denied",
                    tool=fn.__name__,
                    permission=permission,
                    user_id=user.user_id,
                    user_email=user.email,
                )
                raise ToolError(f"Permission denied: requires {permission}")
            return await fn(*args, **kwargs)
        return wrapper
    return decorator
