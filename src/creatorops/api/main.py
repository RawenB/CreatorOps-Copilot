"""FastAPI backend used by the React UI.

Run: uv run uvicorn creatorops.api.main:app --reload --port 8000
Docs: http://localhost:8000/docs
"""

import sqlite3

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from creatorops.agent.graph import Copilot
from creatorops.config import settings
from creatorops.ingestion.parsers import parse_file
from creatorops.tools import tickets
from creatorops.tools.analytics import dashboard
from creatorops.tools.common import get_registry, get_retriever, to_source
from creatorops.tools.scheduling import decide_approval, list_approvals, propose_schedule_post
from creatorops.tools.sql import explain_schema, run_sql


class ChatRequest(BaseModel):
    question: str
    thread_id: str | None = None


class Decision(BaseModel):
    approved: bool
    decided_by: str = "account_manager"


class SqlRequest(BaseModel):
    query: str


class TicketRequest(BaseModel):
    kind: str = "task"  # "task" or "post_request"
    title: str | None = None  # task
    description: str | None = None
    priority: str = "medium"
    assignee: str | None = None
    link: str | None = None
    reference_type: str | None = None
    reference_id: str | None = None
    creator: str | None = None  # post_request
    platform: str | None = None
    post_datetime: str | None = None
    caption: str | None = None


class TicketUpdate(BaseModel):
    status: str | None = None
    priority: str | None = None
    assignee: str | None = None


class SearchRequest(BaseModel):
    query: str
    platform: str | None = None
    doc_type: str | None = None
    as_of: str | None = None
    top_k: int = 5


def create_app(copilot: Copilot | None = None) -> FastAPI:
    app = FastAPI(title="CreatorOps Copilot API", version="0.1")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    state = {"copilot": copilot, "threads": {}}  # threads: approval_id -> thread_id

    def get_copilot() -> Copilot:
        if state["copilot"] is None:
            state["copilot"] = Copilot()
        return state["copilot"]

    def remember_pending(result: dict) -> dict:
        if result["status"] == "waiting_approval":
            state["threads"][result["pending_approval"]["approval_id"]] = result["thread_id"]
        return result

    @app.get("/health")
    def health():
        return {"status": "ok", "llm": settings.llm_provider, "model": settings.ollama_model}

    @app.post("/chat")
    def chat(request: ChatRequest):
        return remember_pending(get_copilot().ask(request.question, request.thread_id))

    @app.get("/approvals")
    def approvals(status: str = "pending"):
        return list_approvals(status)

    @app.post("/approvals/{approval_id}/decision")
    def decide(approval_id: int, decision: Decision):
        # if a chat is waiting for this approval, resume it so the agent can answer
        thread_id = state["threads"].pop(approval_id, None)
        if thread_id:
            return get_copilot().resume(thread_id, decision.approved, decision.decided_by)
        result = decide_approval(approval_id, decision.approved, decision.decided_by)
        if "error" in result:
            raise HTTPException(400, result["error"])
        return {"status": "done", "approval": result}

    @app.get("/tickets")
    def list_all_tickets(kind: str | None = None, status: str | None = None):
        return tickets.list_tickets(kind, status)

    @app.get("/tickets/{ticket_id}")
    def one_ticket(ticket_id: int):
        ticket = tickets.get_ticket(ticket_id)
        if "error" in ticket:
            raise HTTPException(404, ticket["error"])
        return ticket

    @app.post("/tickets")
    def new_ticket(request: TicketRequest):
        """A task, or a post request (which also creates the approval request)."""
        if request.kind == "post_request":
            if not all([request.creator, request.platform, request.post_datetime, request.caption]):
                raise HTTPException(
                    400, "creator, platform, post_datetime and caption are required"
                )
            result = propose_schedule_post(request.creator, request.platform, request.post_datetime,
                                           request.caption, request.link, request.reference_type,
                                           request.reference_id, created_by="user")  # fmt: skip
            if "error" in result:
                raise HTTPException(400, result["error"])
            return tickets.get_ticket(result["ticket_id"])
        if request.kind != "task":
            raise HTTPException(400, "kind must be 'task' or 'post_request'")
        result = tickets.create_task(request.title or "", request.description, request.priority,
                                     request.assignee, request.link, request.reference_type,
                                     request.reference_id, created_by="user")  # fmt: skip
        if "error" in result:
            raise HTTPException(400, result["error"])
        return result

    @app.patch("/tickets/{ticket_id}")
    def change_ticket(ticket_id: int, update: TicketUpdate):
        result = tickets.update_ticket(ticket_id, update.status, update.priority, update.assignee)
        if "error" in result:
            raise HTTPException(400, result["error"])
        return result

    @app.get("/analytics")
    def analytics(platform: str | None = None):
        return dashboard(platform)

    @app.get("/creators")
    def creators():
        """Names for the forms (creator picker)."""
        return run_sql("SELECT creator_id, name, niche, country FROM creators ORDER BY creator_id")[
            "rows"
        ]

    @app.get("/schedule")
    def schedule():
        conn = sqlite3.connect(f"file:{settings.db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            """SELECT s.schedule_id, s.scheduled_at, s.caption, s.status, c.name AS creator,
                      p.name AS platform
               FROM schedule s JOIN creators c ON c.creator_id = s.creator_id
               JOIN platforms p ON p.platform_id = s.platform_id
               ORDER BY s.scheduled_at"""
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]

    @app.post("/sql")
    def sql(request: SqlRequest):
        return run_sql(request.query)

    @app.get("/schema")
    def schema():
        return explain_schema()

    @app.post("/search")
    def search(request: SearchRequest):
        results = get_retriever().search(
            request.query,
            top_k=request.top_k,
            platform=request.platform,
            doc_type=request.doc_type,
            as_of=request.as_of,
        )
        return [to_source(r) for r in results]

    @app.get("/documents/{doc_id}")
    def document(doc_id: str, version: int | None = None):
        """Full text of a document version, so the UI can highlight a cited passage."""
        registry = get_registry()
        versions = registry.versions(doc_id)
        if not versions:
            raise HTTPException(404, "Unknown document")
        version = version or versions[-1][0]
        chunk = registry.first_chunk(doc_id, version)
        if chunk is None:
            raise HTTPException(404, "Unknown version")
        return {
            "doc_id": doc_id,
            "title": chunk["title"],
            "version": version,
            "versions": [
                {"version": v, "snapshot_date": d, "is_latest": bool(latest)}
                for v, d, _, latest in versions
            ],  # fmt: skip
            "source_url": chunk["source_url"],
            "synthetic": chunk["synthetic"],
            "text": parse_file(settings.data_dir / chunk["file_path"]),
        }

    return app


app = create_app()
