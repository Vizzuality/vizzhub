"""Entrypoint: python -m mcp_server"""

from mcp_server.data.base import FULL_ACCESS, set_mcp_user
from mcp_server.server import mcp


def main() -> None:
    set_mcp_user(FULL_ACCESS)
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
