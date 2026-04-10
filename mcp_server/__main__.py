"""Entrypoint: python -m mcp_server"""

from mcp_server.server import mcp


def main() -> None:
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
