"""Small demo: start the CreatorOps MCP server over stdio and call a few tools.

Run: uv run python examples/mcp_client_demo.py
(needs the database and the index: make db corpus ingest)
"""

import asyncio
import json
import os

from mcp import Client, StdioServerParameters


def data(result):
    """Tools return JSON as text content (one block per item for lists)."""
    items = [json.loads(block.text) for block in result.content]
    return items[0] if len(items) == 1 else items


def show(result):
    text = json.dumps(data(result), indent=2)
    print(text[:1200] + ("\n..." if len(text) > 1200 else ""))


async def main():
    server = StdioServerParameters(
        command="uv",
        args=["run", "python", "-m", "creatorops.mcp_server.server"],
        env={**os.environ, "HF_HUB_OFFLINE": "1"},  # models are already downloaded
    )
    async with Client(server) as client:
        tools = await client.list_tools()
        print("Tools:", [t.name for t in tools.tools])

        print("\n--- run_sql: followers per creator on Instagram")
        show(
            await client.call_tool(
                "run_sql",
                {
                    "query": """
            SELECT c.name, a.followers FROM accounts a
            JOIN creators c ON c.creator_id = a.creator_id
            JOIN platforms p ON p.platform_id = a.platform_id
            WHERE p.name = 'Instagram' ORDER BY a.followers DESC LIMIT 5"""
                },
            )
        )

        print("\n--- search_policies: paid partnership label on Instagram")
        result = await client.call_tool(
            "search_policies", {"query": "paid partnership label", "platform": "instagram"}
        )
        for s in data(result)["sources"][:3]:
            print("-", s["title"], "|", s["section"])

        print("\n--- find_clause: exclusivity in contract C003")
        result = await client.call_tool("find_clause", {"clause_type": "exclusivity",
                                                        "contract_id": "C003"})  # fmt: skip
        for s in data(result)["sources"][:2]:
            print("-", s["title"], "|", s["section"], "\n ", s["text"][:200].replace("\n", " "))

        print("\n--- schedule_post (only creates a pending approval)")
        show(await client.call_tool("schedule_post", {
            "creator": "Creator A", "platform": "Instagram",
            "post_datetime": "2030-01-10 18:00", "caption": "New drop! #ad"}))  # fmt: skip


if __name__ == "__main__":
    asyncio.run(main())
