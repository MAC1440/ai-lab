"""Tiny local MCP server for validating AI Lab's MCP manager.

Run from backend:
    python scripts/test_readonly_mcp_server.py

Then add http://127.0.0.1:8001/mcp in AI Lab.
"""

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations


mcp = FastMCP(
    "AI Lab read-only test server",
    host="127.0.0.1",
    port=8001,
    streamable_http_path="/mcp",
)
READ_ONLY = ToolAnnotations(readOnlyHint=True, destructiveHint=False)


@mcp.tool(annotations=READ_ONLY)
def lookup_ai_lab_term(term: str) -> dict[str, str]:
    """Look up a few AI Lab concepts without reading or changing files."""

    glossary = {
        "rag": "Retrieval-augmented generation adds selected references to a model prompt.",
        "proposal": "A reviewable change that is not applied until the user approves it.",
        "mcp": "Model Context Protocol lets an agent consume tools from a separate server.",
    }
    key = term.strip().lower()
    return {"term": key, "definition": glossary.get(key, "No matching test entry.")}


@mcp.tool(annotations=READ_ONLY)
def calculate_sum(a: float, b: float) -> dict[str, float]:
    """Add two numbers; useful for confirming an MCP tool call end to end."""

    return {"a": a, "b": b, "sum": a + b}


if __name__ == "__main__":
    mcp.run(transport="streamable-http")
