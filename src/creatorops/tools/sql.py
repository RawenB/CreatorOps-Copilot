"""Read-only SQL tool over the analytics database.

Safety layers (each one alone would block most attacks, together they are strict):
1. simple checks on the text: one statement, must start with SELECT or WITH
2. the database is opened in read-only mode (sqlite "mode=ro")
3. a SQLite authorizer only allows reading the allowlisted tables (no PRAGMA, ATTACH,
   INSERT, UPDATE, DELETE, CREATE...). SQLite calls it for every action of the query.
4. a progress handler stops queries that run longer than the timeout
5. at most `max_rows` rows are returned
"""

import re
import sqlite3
import time

from creatorops.config import settings

ALLOWED_TABLES = {
    "platforms", "creators", "accounts", "brands", "campaigns", "posts",
    "post_metrics_daily", "schedule", "approvals", "contracts_index",
}  # fmt: skip

TABLE_DESCRIPTIONS = {
    "platforms": "platform_id, name in ('Instagram', 'TikTok', 'YouTube').",
    "creators": "Creators managed by the agency (synthetic personas 'Creator A' to 'Creator H'). "
    "niche = content category.",
    "accounts": "One account per creator per platform. Join: accounts.creator_id = creators.creator_id, "
    "accounts.platform_id = platforms.platform_id.",
    "brands": "Brands that sponsor campaigns. category in ('beauty', 'fashion', 'supplements', 'food', "
    "'tech', 'travel', 'gaming', 'alcohol').",
    "campaigns": "Brand campaigns of a creator (start_date, end_date, budget_usd). "
    "Join: campaigns.brand_id = brands.brand_id, campaigns.creator_id = creators.creator_id.",
    "posts": "Published posts. Join: posts.account_id = accounts.account_id (NOT creator_id). "
    "format in ('reel', 'photo', 'carousel', 'story', 'video', 'short') - Reels are format = 'reel'. "
    "posted_at = 'YYYY-MM-DD HH:MM:SS'. is_paid = 1 for sponsored posts, has_disclosure = 1 if the "
    "paid partnership label was used. campaign_id is NULL for organic posts.",
    "post_metrics_daily": "Metrics of each post for its first 7 days, one row per post per day. "
    "Join: post_metrics_daily.post_id = posts.post_id. To filter by month use posts.posted_at. "
    "Engagement rate = 1.0 * SUM(likes + comments + shares + saves) / SUM(reach) "
    "(multiply by 1.0 to avoid integer division).",
    "schedule": "Posts planned in the future (status 'scheduled').",
    "approvals": "Approval requests for write actions. decision is NULL while pending.",
    "contracts_index": "One row per brand contract (contract_id like 'C003'): start_date, end_date, "
    "fee_usd, exclusivity (1/0) and exclusivity_category. doc_id links to the contract document.",
}

# authorizer action codes that are fine for a read-only query
ALLOWED_ACTIONS = {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION}
if hasattr(sqlite3, "SQLITE_RECURSIVE"):
    ALLOWED_ACTIONS.add(sqlite3.SQLITE_RECURSIVE)  # WITH RECURSIVE


class UnsafeQueryError(Exception):
    pass


def check_query_text(query: str) -> str:
    query = query.strip().rstrip(";").strip()
    if not query:
        raise UnsafeQueryError("Empty query.")
    if ";" in query:
        raise UnsafeQueryError("Only one statement is allowed.")
    if not re.match(r"^(select|with)\b", query, re.IGNORECASE):
        raise UnsafeQueryError("Only SELECT queries are allowed.")
    return query


def make_authorizer(blocked_tables: set[str]):
    """blocked_tables = real tables of the file that are not in the allowlist."""

    def authorizer(action, arg1, arg2, db_name, trigger):
        if action not in ALLOWED_ACTIONS:
            return sqlite3.SQLITE_DENY
        if action == sqlite3.SQLITE_READ and arg1:
            # names that are not real tables are CTE names (WITH x AS ...), those are fine
            if arg1 in blocked_tables or arg1.startswith("sqlite_"):
                return sqlite3.SQLITE_DENY
        return sqlite3.SQLITE_OK

    return authorizer


def run_sql(query: str, db_path=None, max_rows: int | None = None, timeout_s: float | None = None):
    """Run a read-only SELECT query on the analytics database.

    Returns {"query", "columns", "rows", "row_count", "truncated"} or {"error": ...}.
    """
    db_path = db_path or settings.db_path
    max_rows = max_rows or settings.sql_max_rows
    timeout_s = timeout_s or settings.sql_timeout_s

    try:
        query = check_query_text(query)
    except UnsafeQueryError as e:
        return {"query": query, "error": f"Rejected: {e}"}

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    real_tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    conn.set_authorizer(make_authorizer(real_tables - ALLOWED_TABLES))
    deadline = time.time() + timeout_s
    conn.set_progress_handler(lambda: 1 if time.time() > deadline else 0, 10_000)
    try:
        cursor = conn.execute(query)
        rows = cursor.fetchmany(max_rows + 1)
        columns = [d[0] for d in cursor.description] if cursor.description else []
    except sqlite3.DatabaseError as e:
        message = str(e)
        if "not authorized" in message:
            message = "Rejected: query uses a table or action that is not allowed."
        elif "interrupted" in message:
            message = f"Rejected: query took longer than {timeout_s}s."
        return {"query": query, "error": message}
    finally:
        conn.close()

    truncated = len(rows) > max_rows
    rows = [list(r) for r in rows[:max_rows]]
    return {
        "query": query,
        "columns": columns,
        "rows": rows,
        "row_count": len(rows),
        "truncated": truncated,
    }


def explain_schema(db_path=None) -> dict:
    """Describe the tables and columns the SQL tool can use."""
    conn = sqlite3.connect(f"file:{db_path or settings.db_path}?mode=ro", uri=True)
    tables = {}
    for table in sorted(ALLOWED_TABLES):
        columns = conn.execute(f"PRAGMA table_info({table})").fetchall()
        tables[table] = {
            "description": TABLE_DESCRIPTIONS[table],
            "columns": {c[1]: c[2] for c in columns},
        }
    conn.close()
    return {"dialect": "SQLite", "tables": tables}
