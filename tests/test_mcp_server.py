import asyncio
import json

import pytest
from mcp import Client

from creatorops.mcp_server.server import mcp

pytestmark = pytest.mark.usefixtures("tiny_corpus")


def call(name, arguments=None):
    """Call a tool on the server in-process and return the decoded JSON."""

    async def go():
        async with Client(mcp) as client:
            return await client.call_tool(name, arguments or {})

    result = asyncio.run(go())
    items = [json.loads(block.text) for block in result.content]
    return items[0] if len(items) == 1 else items


def test_server_lists_all_tools():
    async def go():
        async with Client(mcp) as client:
            return [t.name for t in (await client.list_tools()).tools]

    names = asyncio.run(go())
    for name in ["search_policies", "compare_policy_versions", "find_clause", "run_sql",
                 "explain_schema", "schedule_post", "list_approvals", "check_post_compliance",
                 "classify_clause", "create_ticket", "list_tickets"]:  # fmt: skip
        assert name in names
    # approving is only possible for a human in the UI / API, not for an MCP client
    assert not any("decide" in n or "approve" in n for n in names)


def test_search_policies_returns_sources():
    result = call("search_policies", {"query": "paid partnership label"})
    assert result["sources"][0]["doc_id"] == "bc"


def test_run_sql_is_read_only():
    assert call("run_sql", {"query": "SELECT COUNT(*) FROM creators"})["rows"] == [[8]]
    assert "error" in call("run_sql", {"query": "DROP TABLE creators"})


def test_schedule_post_only_creates_an_approval():
    result = call("schedule_post", {"creator": "Creator A", "platform": "Instagram",
                                    "post_datetime": "2030-01-10 18:00", "caption": "Hi #ad"})  # fmt: skip
    assert result["status"] == "pending_approval"
    pending = call("list_approvals")
    assert result["approval_id"] in [a["approval_id"] for a in pending]
