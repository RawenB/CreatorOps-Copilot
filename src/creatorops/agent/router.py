"""Decide what kind of question it is, so the agent only gets the tools it needs.

Routes:
- policy:       platform rules, advertising law, agency procedures
- contract:     clauses of brand / talent contracts
- sql:          numbers about creators, posts, campaigns (analytics database)
- hybrid:       needs data AND documents (e.g. best Reel creator + is it allowed for the sponsor)
- action:       the user wants something done (schedule a post)
- out_of_scope: not about the agency's work
"""

import json

from creatorops.agent.prompts import ROUTER_PROMPT

ROUTES = ["policy", "contract", "sql", "hybrid", "action", "out_of_scope"]

ROUTE_TOOLS = {
    "policy": ["search_policies", "compare_policy_versions", "check_post_compliance"],
    "contract": ["find_clause", "run_sql", "explain_schema", "classify_clause"],
    "sql": ["run_sql", "explain_schema"],
    "hybrid": ["search_policies", "compare_policy_versions", "find_clause", "run_sql",
               "explain_schema", "check_post_compliance", "classify_clause", "create_ticket"],
    "action": ["run_sql", "schedule_post", "check_post_compliance", "create_ticket"],
    "out_of_scope": [],
}  # fmt: skip

ALL_TOOLS = ROUTE_TOOLS["hybrid"] + ["schedule_post"]


def keyword_route(question: str) -> str:
    """Simple fallback router (also used by the fake LLM)."""
    q = question.lower()
    if any(
        w in q
        for w in [
            "schedule",
            "plan a post",
            "book a post",
            "publish this",
            "ticket",
            "create a task",
        ]
    ):
        return "action"
    data = any(w in q for w in ["reach", "engagement", "followers", "how many", "average",
                                "which creator", "top ", "best ", "posts", "campaign"])  # fmt: skip
    docs = any(w in q for w in ["allowed", "policy", "rule", "disclos", "label", "guideline",
                                "law", "ftc", "asa", "branded"])  # fmt: skip
    if any(w in q for w in ["contract", "clause", "exclusiv", "non-compete", "termination"]):
        return "hybrid" if data else "contract"
    if data and docs:
        return "hybrid"
    if data:
        return "sql"
    if docs or any(w in q for w in ["instagram", "tiktok", "youtube", "sop", "procedure"]):
        return "policy"
    return "out_of_scope"


def route_question(llm, question: str) -> tuple[str, dict]:
    """Ask the LLM for the route (JSON). Falls back to keywords if the answer is invalid."""
    response = llm.chat(
        [{"role": "system", "content": ROUTER_PROMPT}, {"role": "user", "content": question}],
        json_mode=True,
    )
    try:
        route = json.loads(response["content"]).get("route")
    except (json.JSONDecodeError, AttributeError):
        route = None
    if route not in ROUTES:
        route = keyword_route(question)
    return route, response["usage"]
