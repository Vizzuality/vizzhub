"""Permission enforcement for MCP tools."""

from __future__ import annotations

import functools
import json

from mcp_server.data.base import get_mcp_user


def mcp_requires(permission: str):
    """Decorator that gates an MCP tool behind a permission check.

    Returns a JSON error string if the user lacks the permission.
    Uses functools.wraps to preserve function metadata for FastMCP
    schema introspection (inspect.signature follows __wrapped__).
    """
    def decorator(fn):
        @functools.wraps(fn)
        async def wrapper(*args, **kwargs):
            user = get_mcp_user()
            if not user.has_permission(permission):
                return json.dumps({
                    "error": f"Permission denied: requires {permission}",
                    "user": user.email,
                })
            return await fn(*args, **kwargs)
        return wrapper
    return decorator
