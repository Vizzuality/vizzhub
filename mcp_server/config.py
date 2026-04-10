"""MCP server configuration — reads from environment variables."""

import os


class MCPSettings:
    """Settings for the VizzHub MCP server."""

    def __init__(self) -> None:
        self.database_url: str = os.environ["DATABASE_URL"]
        self.mcp_user_email: str = os.environ.get(
            "MCP_USER_EMAIL", "unknown@vizzuality.com"
        )


_settings: MCPSettings | None = None


def get_settings() -> MCPSettings:
    global _settings
    if _settings is None:
        _settings = MCPSettings()
    return _settings
