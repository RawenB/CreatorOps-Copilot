"""Tools as the LLM sees them (JSON schemas) and how their results are shown to it.

Every result that can be cited gets a number [n]. The LLM must cite these numbers and
citations.py checks that every number in the answer really exists.
"""

from creatorops.tools.classify import classify_clause
from creatorops.tools.compliance import check_post_compliance
from creatorops.tools.contracts import CLAUSE_QUERIES, find_clause
from creatorops.tools.policies import compare_policy_versions, search_policies
from creatorops.tools.sql import explain_schema, run_sql
from creatorops.tools.tickets import PRIORITIES, REFERENCE_TYPES, create_task


def schema(name, description, properties, required):
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {"type": "object", "properties": properties, "required": required},
        },
    }


PLATFORM = {"type": "string", "enum": ["instagram", "tiktok", "youtube"],
            "description": "Platform to filter on (optional)."}  # fmt: skip

TOOL_SCHEMAS = {
    "search_policies": schema(
        "search_policies",
        "Search platform policies (Instagram/Meta, TikTok, YouTube), advertising rules "
        "(FTC, UK ASA/CAP, EU DSA) and the agency's internal procedures.",
        {
            "query": {"type": "string", "description": "What to look for, in plain words."},
            "platform": PLATFORM,
            "as_of": {
                "type": "string",
                "description": "YYYY-MM-DD, only to see the rules valid at a past date.",
            },
        },  # fmt: skip
        ["query"],
    ),
    "compare_policy_versions": schema(
        "compare_policy_versions",
        "Show what changed between the two latest versions of a policy document.",
        {
            "topic": {"type": "string", "description": "Which policy, e.g. 'branded content'."},
            "platform": PLATFORM,
        },  # fmt: skip
        ["topic"],
    ),
    "find_clause": schema(
        "find_clause",
        "Find a type of clause in brand / talent contracts.",
        {
            "clause_type": {"type": "string", "enum": list(CLAUSE_QUERIES)},
            "contract_id": {
                "type": "string",
                "description": "Optional contract id like C003 (from contracts_index).",
            },
            "query": {"type": "string", "description": "Optional extra words."},
        },  # fmt: skip
        ["clause_type"],
    ),
    "run_sql": schema(
        "run_sql",
        "Run ONE read-only SQLite SELECT query on the analytics database "
        "(creators, accounts, posts, post_metrics_daily, campaigns, brands, contracts_index...).",
        {"query": {"type": "string", "description": "A SQLite SELECT query."}},
        ["query"],
    ),
    "explain_schema": schema(
        "explain_schema", "List the tables and columns of the analytics database.", {}, []
    ),
    "check_post_compliance": schema(
        "check_post_compliance",
        "Check a caption before it is posted: disclosure (#ad...) present, clear and at the start, platform "
        "paid-partnership label, prohibited categories, age restriction. Returns a verdict and the rules.",
        {
            "caption": {"type": "string"},
            "platform": {"type": "string", "enum": ["instagram", "tiktok", "youtube"]},
            "is_paid": {"type": "boolean", "description": "Paid OR gifted by a brand."},
            "paid_label_on": {
                "type": "boolean",
                "description": "Platform paid label switched on (if known).",
            },
            "brand_category": {
                "type": "string",
                "description": "e.g. alcohol, tobacco, weight_loss, beauty.",
            },
            "age_restricted": {"type": "boolean", "description": "Age restriction set (if known)."},
        },  # fmt: skip
        ["caption", "platform", "is_paid"],
    ),
    "classify_clause": schema(
        "classify_clause",
        "Classify a contract passage given by the user (exclusivity, non_compete, term_renewal, termination, "
        "ip_license, payment, governing_law, liability, other).",
        {"text": {"type": "string", "description": "The clause text."}},
        ["text"],
    ),
    "create_ticket": schema(
        "create_ticket",
        "Create a task ticket for the team (e.g. 'Add a disclosure to post 166'). Use a reference when the "
        "task is about a contract (C003), campaign (6), post (166), creator (Creator B) or policy document.",
        {
            "title": {"type": "string"},
            "description": {"type": "string"},
            "priority": {"type": "string", "enum": PRIORITIES},
            "reference_type": {"type": "string", "enum": REFERENCE_TYPES},
            "reference_id": {"type": "string", "description": "e.g. C003, 166, Creator B"},
            "link": {"type": "string", "description": "Optional http(s) URL."},
        },  # fmt: skip
        ["title"],
    ),
    "schedule_post": schema(
        "schedule_post",
        "Schedule a post for a creator. This is a write action: a human must approve it "
        "before anything is scheduled.",
        {
            "creator": {"type": "string", "description": "Creator name, e.g. 'Creator A'."},
            "platform": {"type": "string", "enum": ["Instagram", "TikTok", "YouTube"]},
            "post_datetime": {"type": "string", "description": "YYYY-MM-DD HH:MM"},
            "link": {"type": "string", "description": "Optional link to the content draft."},
            "reference_type": {"type": "string", "enum": REFERENCE_TYPES},
            "reference_id": {"type": "string", "description": "e.g. the contract id C003"},
            "caption": {"type": "string"},
        },
        ["creator", "platform", "post_datetime", "caption"],
    ),
}

READ_TOOLS = {
    "search_policies": search_policies,
    "compare_policy_versions": compare_policy_versions,
    "find_clause": find_clause,
    "run_sql": run_sql,
    "explain_schema": explain_schema,
    "check_post_compliance": check_post_compliance,
    "classify_clause": classify_clause,
    # writes only to the team's ticket list (internal, no external effect), so no approval needed
    "create_ticket": lambda **args: create_task(**args, created_by="assistant"),
}

WRITE_TOOLS = {"schedule_post"}


def call_read_tool(name: str, arguments: dict) -> dict:
    if name not in READ_TOOLS:
        return {"error": f"Unknown tool {name}"}
    # small models sometimes send empty strings for optional arguments
    arguments = {k: v for k, v in arguments.items() if v not in ("", None)}
    try:
        return READ_TOOLS[name](**arguments)
    except TypeError as e:
        return {"error": f"Bad arguments for {name}: {e}"}


def result_to_sources(name: str, result: dict, start_n: int) -> list[dict]:
    """Turn a tool result into numbered sources (things the answer can cite)."""
    sources = []
    if "error" in result:
        return sources
    if name in ("search_policies", "find_clause"):
        for s in result["sources"]:
            sources.append({**s, "kind": "document"})
    elif name == "run_sql":
        sources.append({"kind": "sql", "query": result["query"], "columns": result["columns"],
                        "rows": result["rows"], "truncated": result["truncated"]})  # fmt: skip
    elif name == "compare_policy_versions":
        sources.append({"kind": "comparison", **result})
    elif name == "check_post_compliance":
        sources.append(
            {"kind": "compliance", "verdict": result["verdict"], "problems": result["problems"]}
        )
        for s in result.get("sources", []):  # the rule passages, citable like documents
            sources.append({**s, "kind": "document"})
    elif name == "classify_clause":
        sources.append({"kind": "classification", **result})
    elif name == "create_ticket":
        # the ticket has its own "kind" (task): keep it as ticket_kind, the source kind is "ticket"
        sources.append({**result, "ticket_kind": result.get("kind"), "kind": "ticket"})
    for i, s in enumerate(sources):
        s["n"] = start_n + i
    return sources


def format_for_llm(name: str, result: dict, sources: list[dict]) -> str:
    """Compact text version of a tool result for the LLM."""
    if "error" in result:
        return f"ERROR: {result['error']}"
    if name == "explain_schema":
        lines = [f"{t}({', '.join(info['columns'])}): {info['description']}"
                 for t, info in result["tables"].items()]  # fmt: skip
        return "SQLite tables:\n" + "\n".join(lines)
    if not sources:
        return "No results."
    parts = []
    for s in sources:
        if s["kind"] == "document":
            header = f"[{s['n']}] {s['title']}"
            if s.get("section"):
                header += f" | section: {s['section'][-120:]}"
            if s.get("snapshot_date"):
                header += f" | snapshot {s['snapshot_date']} (version {s['version']})"
            if s.get("synthetic"):
                header += " | synthetic document"
            parts.append(header + "\n" + s["text"][:900])
        elif s["kind"] == "sql" and not s["rows"]:
            parts.append(f"[{s['n']}] SQL result: 0 rows. The query matched nothing, so there is "
                         "no data to report (check table joins and column values).")  # fmt: skip
        elif s["kind"] == "sql":
            rows = "\n".join(" | ".join(str(v) for v in r) for r in s["rows"][:30])
            more = " (truncated)" if s["truncated"] or len(s["rows"]) > 30 else ""
            parts.append(
                f"[{s['n']}] SQL result{more}\ncolumns: {' | '.join(s['columns'])}\n{rows}"
            )
        elif s["kind"] == "comparison":
            lines = [f"[{s['n']}] Changes in '{s['title']}' between version "
                     f"{s['old_version']['version']} ({s['old_version']['snapshot_date']}) and "
                     f"version {s['new_version']['version']} ({s['new_version']['snapshot_date']}), "
                     f"{s['n_changes']} changed sections:"]  # fmt: skip
            for c in s["changes"]:
                detail = c.get("diff") or [c.get("new_text") or c.get("old_text")]
                lines.append(f"- {c['change']}: {c['section']}\n  " + "\n  ".join(detail)[:700])
            parts.append("\n".join(lines))
        elif s["kind"] == "compliance":
            problems = (
                "\n".join(f"- {p['rule']}: {p['message']}" for p in s["problems"]) or "- none"
            )
            parts.append(f"[{s['n']}] Compliance check: {s['verdict']}\nproblems:\n{problems}")
        elif s["kind"] == "ticket":
            parts.append(
                f"[{s['n']}] Ticket {s['code']} created: {s['title']} (priority {s['priority']}"
                + (f", reference {s['reference_label']}" if s.get("reference_label") else "")
                + ")"
            )
        elif s["kind"] == "classification":
            parts.append(f"[{s['n']}] Clause classifier: {s['label']} (scores {s['scores']})")
    return "\n\n".join(parts)
