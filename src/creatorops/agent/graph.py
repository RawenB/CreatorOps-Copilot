"""The LangGraph agent.

    START -> router -> (out_of_scope) -> refuse -> END
                    -> agent <-> tools            (tool loop, max MAX_STEPS LLM calls)
                                 tools -> approval -> agent   (interrupt: a human decides)
                       agent -> finalize -> END   (citation check + abstention)

The graph is checkpointed, so a run that stops at the approval step can be resumed later
with Copilot.resume(thread_id, approved=True/False).
"""

import time
import uuid
from datetime import date
from typing import TypedDict

from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from creatorops.agent import citations
from creatorops.agent.prompts import (
    ABSTAIN_ANSWER,
    AGENT_PROMPT,
    OUT_OF_SCOPE_ANSWER,
    SCHEMA_HINT,
)
from creatorops.agent.router import ALL_TOOLS, ROUTE_TOOLS, route_question
from creatorops.agent.tools import (
    TOOL_SCHEMAS,
    call_read_tool,
    format_for_llm,
    result_to_sources,
)
from creatorops.llm.client import get_llm
from creatorops.tools.scheduling import decide_approval, propose_schedule_post
from creatorops.tools.sql import explain_schema

MAX_STEPS = 6


class AgentState(TypedDict, total=False):
    question: str
    route: str
    messages: list[dict]
    last_calls: list[dict]
    sources: list[dict]
    tool_calls: list[dict]  # every tool call, for the trajectory evaluation
    pending: dict | None  # schedule proposal waiting for a human
    approval: dict | None  # the human decision once made
    steps: int
    usage: dict
    answer: str
    citations: list[int]
    invalid_citations: list[int]
    abstained: bool
    unverified: bool


def add_usage(usage: dict, new: dict) -> dict:
    return {
        "llm_calls": usage.get("llm_calls", 0) + 1,
        "prompt_tokens": usage.get("prompt_tokens", 0) + new.get("prompt_tokens", 0),
        "completion_tokens": usage.get("completion_tokens", 0) + new.get("completion_tokens", 0),
    }


def schema_text() -> str:
    tables = explain_schema()["tables"]
    return SCHEMA_HINT.format(
        tables="\n".join(
            f"- {t}({', '.join(info['columns'])}): {info['description']}"
            for t, info in tables.items()
        )
    )


def build_graph(llm=None, use_router: bool = True, checkpointer=None):
    llm = llm or get_llm()

    def tools_for(route: str) -> list[str]:
        return ROUTE_TOOLS.get(route, []) if use_router else ALL_TOOLS

    def router(state: AgentState):
        question = state["question"]
        usage = {}
        if use_router:
            route, router_usage = route_question(llm, question)
            usage = add_usage(usage, router_usage)
        else:
            route = "hybrid"  # ablation: no routing, every tool available
        needs_schema = any(t in tools_for(route) for t in ("run_sql", "schedule_post"))
        system = AGENT_PROMPT.format(
            today=date.today().isoformat(),
            route=route,
            schema=schema_text() if needs_schema else "",
        )
        return {
            "route": route,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": question},
            ],  # fmt: skip
            "sources": [],
            "tool_calls": [],
            "pending": None,
            "approval": None,
            "steps": 0,
            "usage": usage,
        }

    def agent(state: AgentState):
        schemas = [TOOL_SCHEMAS[name] for name in tools_for(state["route"])]
        response = llm.chat(state["messages"], tools=schemas)
        message = {"role": "assistant", "content": response["content"]}
        if response["tool_calls"]:
            message["tool_calls"] = [
                {"function": {"name": c["name"], "arguments": c["arguments"]}}
                for c in response["tool_calls"]
            ]
        return {
            "messages": state["messages"] + [message],
            "last_calls": response["tool_calls"],
            "steps": state["steps"] + 1,
            "usage": add_usage(state["usage"], response["usage"]),
        }

    def after_agent(state: AgentState):
        if state["last_calls"] and state["steps"] < MAX_STEPS:
            return "tools"
        return "finalize"

    def tools(state: AgentState):
        messages = list(state["messages"])
        sources = list(state["sources"])
        log = list(state["tool_calls"])
        pending = None
        allowed = tools_for(state["route"])

        for call in state["last_calls"]:
            name, args = call["name"], call["arguments"]
            log.append({"name": name, "arguments": args})
            if name not in allowed:
                text = f"ERROR: tool {name} is not available for this question."
            elif name == "schedule_post":
                try:
                    result = propose_schedule_post(**args)
                except (TypeError, ValueError) as e:
                    result = {"error": f"Bad arguments for schedule_post: {e}"}
                if "error" in result:
                    text = f"ERROR: {result['error']}"
                else:
                    pending = result
                    text = (f"Approval request #{result['approval_id']} created. "
                            "Waiting for a human to approve it. Nothing is scheduled yet.")  # fmt: skip
            else:
                result = call_read_tool(name, args)
                new_sources = result_to_sources(name, result, start_n=len(sources) + 1)
                sources += new_sources
                text = format_for_llm(name, result, new_sources)
            messages.append({"role": "tool", "content": text, "tool_name": name})
            if pending:
                break  # stop here and ask the human first

        return {"messages": messages, "sources": sources, "tool_calls": log, "pending": pending}

    def after_tools(state: AgentState):
        return "approval" if state.get("pending") else "agent"

    def approval(state: AgentState):
        # the graph stops here; the value passed to resume() comes back from interrupt()
        decision = interrupt({"type": "approval_required", "proposal": state["pending"]})
        approved = bool(decision.get("approved"))
        result = decide_approval(
            state["pending"]["approval_id"], approved, decision.get("decided_by", "user")
        )
        if "error" in result:
            text = f"ERROR: {result['error']}"
        elif approved:
            text = (f"The human APPROVED request #{result['approval_id']}. The post is scheduled "
                    f"(schedule_id {result['schedule_id']}).")  # fmt: skip
        else:
            text = f"The human REJECTED request #{result['approval_id']}. Nothing was scheduled."
        messages = state["messages"] + [{"role": "tool", "content": text,
                                          "tool_name": "schedule_post"}]  # fmt: skip
        return {"messages": messages, "pending": None, "approval": result}

    def finalize(state: AgentState):
        answer = state["messages"][-1].get("content") or ""
        if state["messages"][-1]["role"] != "assistant":
            answer = ""
        check = citations.verify(answer, state["sources"], state["route"])
        if check["abstained"] and not citations.looks_like_abstention(answer):
            check["answer"] = ABSTAIN_ANSWER
        if not answer.strip():
            check.update(answer=ABSTAIN_ANSWER, abstained=True, unverified=False)
        return check

    def refuse(state: AgentState):
        return {"answer": OUT_OF_SCOPE_ANSWER, "abstained": True, "citations": [],
                "invalid_citations": [], "unverified": False}  # fmt: skip

    graph = StateGraph(AgentState)
    graph.add_node("router", router)
    graph.add_node("agent", agent)
    graph.add_node("tools", tools)
    graph.add_node("approval", approval)
    graph.add_node("finalize", finalize)
    graph.add_node("refuse", refuse)
    graph.add_edge(START, "router")
    graph.add_conditional_edges(
        "router", lambda s: "refuse" if s["route"] == "out_of_scope" else "agent"
    )
    graph.add_conditional_edges("agent", after_agent)
    graph.add_conditional_edges("tools", after_tools)
    graph.add_edge("approval", "agent")
    graph.add_edge("finalize", END)
    graph.add_edge("refuse", END)
    return graph.compile(checkpointer=checkpointer or InMemorySaver())


class Copilot:
    """Small wrapper used by the API, the eval scripts and the CLI."""

    def __init__(self, llm=None, use_router: bool = True):
        self.graph = build_graph(llm=llm, use_router=use_router)

    def ask(self, question: str, thread_id: str | None = None) -> dict:
        thread_id = thread_id or str(uuid.uuid4())
        start = time.time()
        self.graph.invoke({"question": question}, self.config(thread_id))
        return self.result(thread_id, time.time() - start)

    def resume(self, thread_id: str, approved: bool, decided_by: str = "user") -> dict:
        start = time.time()
        self.graph.invoke(
            Command(resume={"approved": approved, "decided_by": decided_by}),
            self.config(thread_id),
        )
        return self.result(thread_id, time.time() - start)

    @staticmethod
    def config(thread_id: str) -> dict:
        return {"configurable": {"thread_id": thread_id}, "recursion_limit": 40}

    def result(self, thread_id: str, seconds: float) -> dict:
        state = self.graph.get_state(self.config(thread_id))
        values = state.values
        waiting = bool(state.next)  # the graph stopped at the approval step
        return {
            "thread_id": thread_id,
            "status": "waiting_approval" if waiting else "done",
            "question": values.get("question"),
            "route": values.get("route"),
            "answer": None if waiting else values.get("answer"),
            "pending_approval": values.get("pending") if waiting else None,
            "approval": values.get("approval"),
            "citations": values.get("citations", []),
            "invalid_citations": values.get("invalid_citations", []),
            "abstained": values.get("abstained", False),
            "unverified": values.get("unverified", False),
            "sources": values.get("sources", []),
            "tool_calls": values.get("tool_calls", []),
            "usage": values.get("usage", {}),
            "latency_s": round(seconds, 2),
        }
