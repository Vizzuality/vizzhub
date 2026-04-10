"""MCP server definition — registers tools from each module."""

from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "VizzHub",
    instructions=(
        "VizzHub is Vizzuality's internal operations hub. "
        "Use the ISO tools to query compliance registries and documents. "
        "Registry slugs are listed by iso_get_registries. "
        "Document content can be searched with iso_search_documents."
    ),
)
