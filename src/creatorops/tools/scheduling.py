"""The only write action: scheduling a post. It always goes through a human approval.

1. propose_schedule_post() checks the request and creates a *pending* row in `approvals`.
   Nothing is scheduled yet.
2. A person approves or rejects it (in the UI, the API or the MCP client).
3. decide_approval() records the decision, and only if it is approved adds the post to `schedule`.

This module uses its own normal (writable) connection. The SQL tool can never write.
"""

import json
import sqlite3
from datetime import datetime

from creatorops.config import settings

PLATFORMS = ["Instagram", "TikTok", "YouTube"]


def connect(db_path=None):
    return sqlite3.connect(db_path or settings.db_path)


def now() -> str:
    return datetime.now().isoformat(sep=" ", timespec="seconds")


def propose_schedule_post(
    creator_id: int, platform: str, post_datetime: str, caption: str, db_path=None
) -> dict:
    """Validate a scheduling request and store it as a pending approval."""
    platform = (
        platform.strip().capitalize().replace("Tiktok", "TikTok").replace("Youtube", "YouTube")
    )
    if platform not in PLATFORMS:
        return {"error": f"Unknown platform {platform!r}. Use one of {PLATFORMS}."}
    try:
        when = datetime.fromisoformat(post_datetime.replace("T", " "))
    except ValueError:
        return {"error": "post_datetime must look like 'YYYY-MM-DD HH:MM'."}
    if when <= datetime.now():
        return {"error": f"{when} is in the past, a post can only be scheduled in the future."}
    if not caption.strip():
        return {"error": "The caption is empty."}

    conn = connect(db_path)
    creator = conn.execute(
        "SELECT name FROM creators WHERE creator_id = ?", (int(creator_id),)
    ).fetchone()
    if creator is None:
        conn.close()
        return {"error": f"No creator with creator_id {creator_id}."}

    details = {
        "creator_id": int(creator_id),
        "creator_name": creator[0],
        "platform": platform,
        "post_datetime": when.isoformat(sep=" ", timespec="minutes"),
        "caption": caption.strip(),
    }
    cursor = conn.execute(
        "INSERT INTO approvals (schedule_id, action, requested_at, details) VALUES (NULL, ?, ?, ?)",
        ("schedule_post", now(), json.dumps(details)),
    )
    conn.commit()
    conn.close()
    return {"approval_id": cursor.lastrowid, "status": "pending_approval", **details}


def decide_approval(approval_id: int, approved: bool, decided_by: str = "user", db_path=None):
    """Record the human decision. Writes to `schedule` only when approved."""
    conn = connect(db_path)
    row = conn.execute(
        "SELECT decision, details FROM approvals WHERE approval_id = ? AND action = 'schedule_post'",
        (approval_id,),
    ).fetchone()
    if row is None:
        conn.close()
        return {"error": f"No approval request {approval_id}."}
    if row[0] is not None:
        conn.close()
        return {"error": f"Approval {approval_id} was already {row[0]}."}

    details = json.loads(row[1])
    schedule_id = None
    if approved:
        platform_id = PLATFORMS.index(details["platform"]) + 1
        cursor = conn.execute(
            "INSERT INTO schedule (creator_id, platform_id, scheduled_at, caption, status, created_at)"
            " VALUES (?, ?, ?, ?, 'scheduled', ?)",
            (
                details["creator_id"],
                platform_id,
                details["post_datetime"],
                details["caption"],
                now(),
            ),
        )
        schedule_id = cursor.lastrowid
    conn.execute(
        "UPDATE approvals SET decision = ?, decided_at = ?, decided_by = ?, schedule_id = ? "
        "WHERE approval_id = ?",
        ("approved" if approved else "rejected", now(), decided_by, schedule_id, approval_id),
    )
    conn.commit()
    conn.close()
    return {
        "approval_id": approval_id,
        "decision": "approved" if approved else "rejected",
        "schedule_id": schedule_id,
        **details,
    }


def list_approvals(status: str = "pending", db_path=None) -> list[dict]:
    """status: "pending", "approved", "rejected" or "all"."""
    conn = connect(db_path)
    query = "SELECT approval_id, action, requested_at, decision, decided_at, decided_by, details FROM approvals"
    if status == "pending":
        query += " WHERE decision IS NULL"
    elif status in ("approved", "rejected"):
        query += f" WHERE decision = '{status}'"
    rows = conn.execute(query + " ORDER BY approval_id DESC").fetchall()
    conn.close()
    keys = ["approval_id", "action", "requested_at", "decision", "decided_at", "decided_by"]
    return [{**dict(zip(keys, r[:6])), **json.loads(r[6] or "{}")} for r in rows]
