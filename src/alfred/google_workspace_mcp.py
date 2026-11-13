"""Google Workspace MCP server: Google Calendar and Google Tasks, with room for Gmail."""

from fastmcp import FastMCP

from alfred import calendar_mcp, tasks_mcp

mcp = FastMCP(
    name="google-workspace",
    instructions=f"{calendar_mcp.INSTRUCTIONS} {tasks_mcp.INSTRUCTIONS}",
)
mcp.mount(calendar_mcp.mcp)
mcp.mount(tasks_mcp.mcp)


if __name__ == "__main__":
    mcp.run(transport="stdio")
