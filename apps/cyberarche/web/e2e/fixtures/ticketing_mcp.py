"""External MCP fixture server for e2e: a fictional ticketing system.

Booted by playwright.config.ts so the connectors settings e2e can attach
a REAL MCP server over Streamable HTTP.
"""

from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import PlainTextResponse

mcp = FastMCP(name="ticketing", instructions="Cyberdyne ticketing system tools")

TICKETS = {
    "TCK-42": {"status": "in_review", "assignee": "Mira Kato", "priority": "high"},
    "TCK-7": {"status": "done", "assignee": "Tomás", "priority": "low"},
}


@mcp.tool
def get_ticket_status(ticket_id: str) -> dict:
    """Look up a ticket's status, assignee, and priority by its id."""
    ticket = TICKETS.get(ticket_id.upper())
    if ticket is None:
        return {"error": f"no ticket {ticket_id}"}
    return {"ticket_id": ticket_id.upper(), **ticket}


@mcp.custom_route("/health", methods=["GET"])
async def health(request: Request) -> PlainTextResponse:
    return PlainTextResponse("ok")


if __name__ == "__main__":
    mcp.run(transport="http", host="127.0.0.1", port=8200)
