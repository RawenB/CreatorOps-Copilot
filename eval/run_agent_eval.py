"""Agent benchmark: runs every question through the full agent (router + tools + LLM).

Measures routing accuracy, tool-call accuracy, trajectory, SQL execution accuracy, approval
interrupts, abstention, keyword correctness, citations, latency and tokens.
The LLM-judge metrics (faithfulness, correctness) are in run_generation_eval.py.

Each question runs on a fresh copy of the analytics database, so questions don't change
each other's data (scheduling requests write to the approvals table).

Run:  uv run python eval/run_agent_eval.py                  (all questions, ~40 min)
      uv run python eval/run_agent_eval.py --limit 10 --types sql,policy
      uv run python eval/run_agent_eval.py --no-router --name agent_no_router
Results are written line by line, so --resume continues a run that stopped.
"""

import argparse
import json
import shutil
import sqlite3
import traceback
from pathlib import Path

from creatorops.agent.graph import Copilot
from creatorops.config import settings
from creatorops.evaluation.dataset import load_questions
from creatorops.evaluation.metrics import (
    keyword_score,
    mean,
    percentile,
    precision_recall,
    sql_result_matches,
    trajectory_ok,
)
from creatorops.tools.sql import run_sql

RUNS = Path("eval/runs")
ORIGINAL_DB = settings.db_path
EVAL_DB = RUNS / "eval_db.sqlite"


def count(db, query):
    conn = sqlite3.connect(db)
    value = conn.execute(query).fetchone()[0]
    conn.close()
    return value


def compact_source(s: dict) -> dict:
    if s["kind"] == "document":
        return {"n": s["n"], "kind": "document", "doc_id": s["doc_id"], "version": s.get("version"),
                "section": s.get("section"), "text": s["text"][:1500]}  # fmt: skip
    if s["kind"] == "sql":
        return {"n": s["n"], "kind": "sql", "query": s["query"], "columns": s["columns"],
                "rows": s["rows"][:50]}  # fmt: skip
    return {"n": s["n"], "kind": s["kind"], "doc_id": s.get("doc_id"),
            "changes": s.get("changes", [])[:5]}  # fmt: skip


def run_one(copilot: Copilot, item: dict) -> dict:
    shutil.copy(ORIGINAL_DB, EVAL_DB)  # fresh data for every question
    schedule_before = count(EVAL_DB, "SELECT COUNT(*) FROM schedule")
    pending_before = count(EVAL_DB, "SELECT COUNT(*) FROM approvals WHERE decision IS NULL")
    try:
        r = copilot.ask(item["question"])
        error = None
    except Exception:
        r, error = {}, traceback.format_exc(limit=3)
    return {
        "id": item["id"],
        "type": item["type"],
        "question": item["question"],
        "route": r.get("route"),
        "status": r.get("status"),
        "answer": r.get("answer"),
        "abstained": r.get("abstained", False),
        "unverified": r.get("unverified", False),
        "citations": r.get("citations", []),
        "invalid_citations": r.get("invalid_citations", []),
        "tool_calls": r.get("tool_calls", []),
        "sources": [compact_source(s) for s in r.get("sources", [])],
        "pending_approval": r.get("pending_approval"),
        "schedule_changed": count(EVAL_DB, "SELECT COUNT(*) FROM schedule") != schedule_before,
        "new_pending": count(EVAL_DB, "SELECT COUNT(*) FROM approvals WHERE decision IS NULL")
        - pending_before,
        "latency_s": r.get("latency_s"),
        "usage": r.get("usage", {}),
        "error": error,
    }


def summarize(rows: list[dict], items: list[dict]) -> dict:
    by_id = {i["id"]: i for i in items}
    rows = [r for r in rows if r["id"] in by_id]
    s = {"n": len(rows), "errors": sum(1 for r in rows if r["error"])}

    # routing
    routed = [r for r in rows if by_id[r["id"]]["expected_route"]]
    s["routing_accuracy"] = mean(r["route"] == by_id[r["id"]]["expected_route"] for r in routed)

    # tools: recall = all expected tools were called, precision = called tools that were expected
    with_tools = [r for r in rows if by_id[r["id"]]["expected_tools"]]
    names = {r["id"]: [c["name"] for c in r["tool_calls"]] for r in rows}
    s["tool_recall"] = mean(
        set(by_id[r["id"]]["expected_tools"]) <= set(names[r["id"]]) for r in with_tools
    )
    s["tool_precision"] = mean(
        mean(n in by_id[r["id"]]["expected_tools"] for n in names[r["id"]])
        for r in with_tools
        if names[r["id"]]
    )
    s["trajectory_accuracy"] = mean(
        trajectory_ok(names[r["id"]], by_id[r["id"]]["expected_tools"]) for r in with_tools
    )

    # SQL execution accuracy: one of the agent's SQL results equals the gold result
    with_sql = [r for r in rows if by_id[r["id"]]["gold_sql"] and r["type"] in ("sql", "hybrid")]
    exec_ok = []
    for r in with_sql:
        gold = run_sql(by_id[r["id"]]["gold_sql"], db_path=ORIGINAL_DB)["rows"]
        preds = [src["rows"] for src in r["sources"] if src["kind"] == "sql"]
        r["sql_correct"] = any(sql_result_matches(gold, p) for p in preds)
        exec_ok.append(r)
    s["sql_execution_accuracy"] = {
        t: mean(r["sql_correct"] for r in exec_ok if r["type"] == t)
        for t in ("sql", "hybrid")
        if any(r["type"] == t for r in exec_ok)
    }

    # approvals
    must_wait = [r for r in rows if by_id[r["id"]]["expected_status"] == "waiting_approval"]
    s["approval_interrupt_rate"] = mean(
        r["status"] == "waiting_approval" and not r["schedule_changed"] for r in must_wait
    )
    bad_actions = [r for r in rows if r["type"] == "action" and r["id"] not in
                   {m["id"] for m in must_wait}]  # fmt: skip
    s["invalid_action_refused_rate"] = mean(r["new_pending"] == 0 for r in bad_actions)
    s["writes_without_approval"] = sum(r["schedule_changed"] for r in rows)

    # abstention: predicted = abstained (includes out-of-scope refusals)
    gold = [by_id[r["id"]]["should_abstain"] for r in rows]
    s["abstention"] = precision_recall([bool(r["abstained"]) for r in rows], gold)

    # answers (keywords) and citations, for questions that have an answer to check
    answerable = [r for r in rows if r["type"] in ("policy", "contract", "sql", "hybrid")]
    for r in answerable:
        r["keyword_score"] = keyword_score(r["answer"], by_id[r["id"]]["must_include"])
    s["keyword_correctness"] = {
        t: mean(r["keyword_score"] for r in answerable if r["type"] == t)
        for t in ("policy", "contract", "sql", "hybrid")
        if any(r["type"] == t for r in answerable)
    }
    s["keyword_correctness"]["all"] = mean(r["keyword_score"] for r in answerable)

    doc_cites, has_gold_cite = [], []
    for r in answerable:
        gold_docs = set(by_id[r["id"]]["gold_doc_ids"])
        if not gold_docs:
            continue
        sources = {src["n"]: src for src in r["sources"]}
        cited_docs = [sources[n]["doc_id"] for n in r["citations"]
                      if n in sources and sources[n]["kind"] != "sql"]  # fmt: skip
        doc_cites += [d in gold_docs for d in cited_docs]
        has_gold_cite.append(any(d in gold_docs for d in cited_docs))
    s["citation_precision"] = mean(doc_cites)  # cited documents that are gold documents
    s["citation_recall"] = mean(has_gold_cite)  # answers citing at least one gold document
    s["invalid_citation_rate"] = mean(bool(r["invalid_citations"]) for r in answerable)
    s["unverified_rate"] = mean(r["unverified"] for r in answerable)

    # cost
    latencies = [r["latency_s"] for r in rows if r["latency_s"] is not None]
    s["latency_s"] = {"mean": mean(latencies), "p50": percentile(latencies, 50),
                      "p95": percentile(latencies, 95)}  # fmt: skip
    s["tokens_per_question"] = {
        "prompt": mean(r["usage"].get("prompt_tokens", 0) for r in rows),
        "completion": mean(r["usage"].get("completion_tokens", 0) for r in rows),
        "llm_calls": mean(r["usage"].get("llm_calls", 0) for r in rows),
    }
    return round_all(s)


def round_all(x):
    if isinstance(x, float):
        return round(x, 3)
    if isinstance(x, dict):
        return {k: round_all(v) for k, v in x.items()}
    return x


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--name", default="agent")
    parser.add_argument("--types", help="comma separated, e.g. sql,policy")
    parser.add_argument("--limit", type=int)
    parser.add_argument("--no-router", action="store_true")
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()

    items = load_questions(types=args.types.split(",") if args.types else None, limit=args.limit)
    out = RUNS / f"{args.name}.jsonl"
    RUNS.mkdir(parents=True, exist_ok=True)
    done = set()
    if args.resume and out.exists():
        done = {json.loads(line)["id"] for line in out.read_text().splitlines()}
    elif out.exists():
        out.unlink()

    settings.db_path = EVAL_DB  # every tool now reads/writes the copy
    copilot = Copilot(use_router=not args.no_router)
    for i, item in enumerate(items, 1):
        if item["id"] in done:
            continue
        row = run_one(copilot, item)
        with out.open("a") as f:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"[{i}/{len(items)}] {item['id']} route={row['route']} status={row['status']} "
              f"{row['latency_s']}s {'ERROR' if row['error'] else ''}", flush=True)  # fmt: skip

    rows = [json.loads(line) for line in out.read_text().splitlines()]
    summary = summarize(rows, items)
    (RUNS / f"{args.name}_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
