"""Tickets: the team's to-do list, with a link and a reference to the data they are about.

Two kinds:
- "task": something to do (e.g. "Fix Creator B's undisclosed posts"), status open -> in_progress -> done
- "post_request": created automatically for every scheduling request (from the UI, the agent or an
  MCP client). Its status follows the human approval (pending / approved / rejected), so a ticket
  can never be closed without the approval.

A reference points to something that exists: a contract (C003), a campaign (6), a post (166), a
creator (Creator B) or a policy document (ftc_disclosures_101). It is checked when the ticket is
created, so a ticket never points to nothing. The link is any http(s) URL (content draft, brief...).
"""

import re
import sqlite3
from datetime import datetime

from creatorops.config import settings

KINDS = ["task", "post_request"]
TASK_STATUSES = ["open", "in_progress", "done"]
PRIORITIES = ["low", "medium", "high"]
REFERENCE_TYPES = ["contract", "campaign", "post", "creator", "policy"]

CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS tickets (
    ticket_id INTEGER PRIMARY KEY,
    kind TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    status TEXT NOT NULL,
    priority TEXT NOT NULL DEFAULT 'medium',
    assignee TEXT,
    link TEXT,
    reference_type TEXT,
    reference_id TEXT,
    reference_label TEXT,
    approval_id INTEGER REFERENCES approvals(approval_id),
    created_by TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)"""


def connect(db_path=None):
    conn = sqlite3.connect(db_path or settings.db_path)
    conn.execute(CREATE_TABLE)  # older databases don't have the table yet
    return conn


def now() -> str:
    return datetime.now().isoformat(sep=" ", timespec="seconds")


def code(ticket_id: int) -> str:
    return f"TCK-{ticket_id:04d}"


def check_link(link: str | None) -> str | None:
    """Return an error message, or None if the link is fine (or empty)."""
    if link and not re.match(r"^https?://[^\s/$.?#].[^\s]*$", link.strip()):
        return "The link must be a full URL starting with http:// or https://"
    return None


def resolve_reference(conn, ref_type: str | None, ref_id) -> dict:
    """Check that the reference exists. Returns {type, id, label, doc_id?} or {error}."""
    if not ref_type:
        return {}
    ref_type = ref_type.lower().strip()
    ref_id = str(ref_id or "").strip()
    if ref_type not in REFERENCE_TYPES:
        return {"error": f"reference_type must be one of {REFERENCE_TYPES}"}
    if not ref_id:
        return {"error": "reference_id is missing"}

    if ref_type == "contract":
        row = conn.execute(
            "SELECT ci.contract_id, ci.doc_id, b.name, c.name FROM contracts_index ci "
            "JOIN brands b ON b.brand_id = ci.brand_id JOIN creators c ON c.creator_id = ci.creator_id "
            "WHERE ci.contract_id = ?",
            (ref_id.upper(),),
        ).fetchone()
        if row:
            return {
                "type": "contract",
                "id": row[0],
                "doc_id": row[1],
                "label": f"Contract {row[0]} ({row[2]} x {row[3]})",
            }
    elif ref_type == "campaign":
        row = conn.execute(
            "SELECT campaign_id, name FROM campaigns WHERE campaign_id = ? OR lower(name) = lower(?)",
            (int(ref_id) if ref_id.isdigit() else -1, ref_id),
        ).fetchone()
        if row:
            return {"type": "campaign", "id": str(row[0]), "label": f"Campaign {row[1]}"}
    elif ref_type == "post":
        row = conn.execute(
            "SELECT p.post_id, c.name, p.posted_at FROM posts p JOIN accounts a ON a.account_id = p.account_id "
            "JOIN creators c ON c.creator_id = a.creator_id WHERE p.post_id = ?",
            (int(ref_id) if ref_id.isdigit() else -1,),
        ).fetchone()
        if row:
            return {
                "type": "post",
                "id": str(row[0]),
                "label": f"Post {row[0]} by {row[1]} ({row[2][:10]})",
            }
    elif ref_type == "creator":
        row = conn.execute(
            "SELECT creator_id, name FROM creators WHERE lower(name) = lower(?) OR creator_id = ?",
            (ref_id, int(ref_id) if ref_id.isdigit() else -1),
        ).fetchone()
        if row:
            return {"type": "creator", "id": row[1], "label": row[1]}
    elif ref_type == "policy":
        from creatorops.tools.common import get_registry

        registry = get_registry()
        versions = registry.versions(ref_id)
        if versions:
            chunk = registry.first_chunk(ref_id, versions[-1][0])
            return {"type": "policy", "id": ref_id, "doc_id": ref_id, "label": chunk["title"]}
    return {"error": f"No {ref_type} '{ref_id}' found."}


def insert_ticket(conn, kind, title, created_by, description=None, status="open", priority="medium",
                  assignee=None, link=None, reference=None, approval_id=None) -> int:  # fmt: skip
    reference = reference or {}
    cursor = conn.execute(
        "INSERT INTO tickets (kind, title, description, status, priority, assignee, link, reference_type, "
        "reference_id, reference_label, approval_id, created_by, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            kind,
            title,
            description,
            status,
            priority,
            assignee,
            (link or "").strip() or None,
            reference.get("type"),
            reference.get("id"),
            reference.get("label"),
            approval_id,
            created_by,
            now(),
            now(),
        ),  # fmt: skip
    )
    return cursor.lastrowid


def create_task(
    title: str,
    description: str | None = None,
    priority: str = "medium",
    assignee: str | None = None,
    link: str | None = None,
    reference_type: str | None = None,
    reference_id: str | None = None,
    created_by: str = "user",
    db_path=None,
) -> dict:
    """Create a task ticket. Returns the ticket or {error}."""
    if not title or not title.strip():
        return {"error": "The title is empty."}
    if priority not in PRIORITIES:
        return {"error": f"priority must be one of {PRIORITIES}"}
    if error := check_link(link):
        return {"error": error}
    conn = connect(db_path)
    reference = resolve_reference(conn, reference_type, reference_id)
    if "error" in reference:
        conn.close()
        return reference
    ticket_id = insert_ticket(conn, "task", title.strip(), created_by, description, "open", priority,
                              assignee, link, reference)  # fmt: skip
    conn.commit()
    conn.close()
    return get_ticket(ticket_id, db_path)


def get_ticket(ticket_id: int, db_path=None) -> dict:
    tickets = list_tickets(ticket_id=ticket_id, db_path=db_path)
    return tickets[0] if tickets else {"error": f"No ticket {ticket_id}."}


def list_tickets(kind=None, status=None, ticket_id=None, db_path=None) -> list[dict]:
    """Tickets, newest first. The status of a post request comes from its approval."""
    conn = connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT t.*, a.decision, a.decided_by, a.decided_at FROM tickets t "
        "LEFT JOIN approvals a ON a.approval_id = t.approval_id ORDER BY t.ticket_id DESC"
    ).fetchall()
    conn.close()
    result = []
    for r in rows:
        t = dict(r)
        if t["kind"] == "post_request":
            t["status"] = t["decision"] or "pending"
        t["code"] = code(t["ticket_id"])
        if t["reference_type"] == "contract" and t["reference_id"]:
            t["reference_doc_id"] = _contract_doc_id(t["reference_id"], db_path)
        elif t["reference_type"] == "policy":
            t["reference_doc_id"] = t["reference_id"]
        if ticket_id is not None and t["ticket_id"] != ticket_id:
            continue
        if kind and t["kind"] != kind:
            continue
        if status and t["status"] != status:
            continue
        result.append(t)
    return result


def _contract_doc_id(contract_id: str, db_path=None) -> str | None:
    conn = sqlite3.connect(db_path or settings.db_path)
    row = conn.execute(
        "SELECT doc_id FROM contracts_index WHERE contract_id = ?", (contract_id,)
    ).fetchone()
    conn.close()
    return row[0] if row else None


def update_ticket(ticket_id: int, status=None, priority=None, assignee=None, db_path=None) -> dict:
    """Change a task's status / priority / assignee. Post requests follow their approval."""
    ticket = get_ticket(ticket_id, db_path)
    if "error" in ticket:
        return ticket
    if status is not None:
        if ticket["kind"] == "post_request":
            return {
                "error": "The status of a post request changes with its approval (Approvals page)."
            }
        if status not in TASK_STATUSES:
            return {"error": f"status must be one of {TASK_STATUSES}"}
    if priority is not None and priority not in PRIORITIES:
        return {"error": f"priority must be one of {PRIORITIES}"}
    conn = connect(db_path)
    for column, value in (("status", status), ("priority", priority), ("assignee", assignee)):
        if value is not None:
            conn.execute(f"UPDATE tickets SET {column} = ?, updated_at = ? WHERE ticket_id = ?",
                         (value, now(), ticket_id))  # fmt: skip
    conn.commit()
    conn.close()
    return get_ticket(ticket_id, db_path)
