"""Google Workspace MCP server: Google Calendar today, with room for Tasks and Gmail."""

from fastmcp import FastMCP

from alfred import calendar_mcp

mcp = FastMCP(name="google-workspace", instructions=calendar_mcp.INSTRUCTIONS)
mcp.mount(calendar_mcp.mcp)


if __name__ == "__main__":
    mcp.run(transport="stdio")
