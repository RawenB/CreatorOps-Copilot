"""MCP server: the same tools as the agent, for any MCP client (Claude Desktop, Cursor, ...).

Run (stdio): uv run python -m creatorops.mcp_server.server

schedule_post never schedules anything by itself: it creates a pending approval that a human
has to accept in the React UI (or with POST /approvals/{id}/decision). The MCP client can
only look at approvals, not decide them.
"""

from mcp.server.mcpserver import MCPServer

from creatorops.tools import contracts, policies, scheduling, sql

mcp = MCPServer("creatorops")


@mcp.tool()
def search_policies(query: str, platform: str | None = None, as_of: str | None = None) -> dict:
    """Search platform policies (Instagram/Meta, TikTok, YouTube), advertising rules
    (FTC, UK ASA/CAP, EU DSA) and the agency's internal procedures.

    platform: "instagram", "tiktok" or "youtube" (optional).
    as_of: "YYYY-MM-DD" to see the rules that were valid at that date (optional).
    """
    return policies.search_policies(query, platform=platform, as_of=as_of)


@mcp.tool()
def compare_policy_versions(topic: str, platform: str | None = None) -> dict:
    """Show what changed between the two latest versions of a policy (e.g. "branded content")."""
    return policies.compare_policy_versions(topic, platform=platform)


@mcp.tool()
def find_clause(clause_type: str, contract_id: str | None = None, query: str | None = None) -> dict:
    """Find a type of clause in brand / talent contracts.

    clause_type: exclusivity, non_compete, term_renewal, termination, ip_license, payment,
    governing_law or confidentiality.
    contract_id: optional, like "C003" (see the contracts_index table).
    """
    return contracts.find_clause(clause_type, contract_id=contract_id, query=query)


@mcp.tool()
def run_sql(query: str) -> dict:
    """Run ONE read-only SQLite SELECT on the analytics database (creators, posts,
    post_metrics_daily, campaigns, brands, contracts_index...). Call explain_schema first."""
    return sql.run_sql(query)


@mcp.tool()
def explain_schema() -> dict:
    """Tables, columns and join keys of the analytics database."""
    return sql.explain_schema()


@mcp.tool()
def schedule_post(creator_id: int, platform: str, post_datetime: str, caption: str) -> dict:
    """Ask to schedule a post. Nothing is scheduled until a human approves the request.

    platform: Instagram, TikTok or YouTube. post_datetime: "YYYY-MM-DD HH:MM" in the future.
    """
    result = scheduling.propose_schedule_post(creator_id, platform, post_datetime, caption)
    if "error" not in result:
        result["note"] = "Waiting for human approval in the CreatorOps UI."
    return result


@mcp.tool()
def list_approvals(status: str = "pending") -> list[dict]:
    """List approval requests. status: pending, approved or rejected."""
    return scheduling.list_approvals(status)


@mcp.resource("creatorops://schema")
def schema_resource() -> str:
    """The analytics database schema as text."""
    tables = sql.explain_schema()["tables"]
    return "\n".join(f"{name}: {', '.join(t['columns'])}" for name, t in tables.items())


def main():
    mcp.run()


if __name__ == "__main__":
    main()
