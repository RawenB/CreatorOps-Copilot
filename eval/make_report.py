"""Collect the summaries of the eval runs into reports/eval_results.md (+ copies of the JSON).

Run: uv run python eval/make_report.py
"""

import json
import shutil
from datetime import date
from pathlib import Path

from creatorops.config import settings

RUNS = Path("eval/runs")
REPORTS = Path("reports")
OUT = REPORTS / "eval"


def load(name):
    path = RUNS / f"{name}_summary.json"
    return json.loads(path.read_text()) if path.exists() else None


def pct(x):
    return "n/a" if x is None else f"{100 * x:.1f}%"


def retrieval_section(lines):
    runs = sorted(
        p.name.removesuffix("_summary.json") for p in RUNS.glob("retrieval_*_summary.json")
    )
    if not runs:
        return
    lines += ["## Retrieval", "",
              "Gold = the chunk is from a gold document (right version) and contains a gold passage.", "",
              "| run | type | n | Recall@1 | Recall@5 | Recall@10 | MRR | nDCG@10 | s/query |",
              "|---|---|---|---|---|---|---|---|---|"]  # fmt: skip
    for run in runs:
        s = load(run)
        for t, m in s.items():
            if isinstance(m, dict):
                lines.append(f"| {run.removeprefix('retrieval_')} | {t} | {m['n']} | {m['recall@1']:.3f} | "
                             f"{m['recall@5']:.3f} | {m['recall@10']:.3f} | {m['mrr']:.3f} | "
                             f"{m['ndcg@10']:.3f} | {s['seconds_per_query']} |")  # fmt: skip
    lines.append("")


def agent_section(lines, name="agent"):
    s = load(name)
    if not s:
        return
    a = s["abstention"]
    lines += [f"## Agent ({name}, {s['n']} questions, {s['errors']} crashes)", "",
              "| metric | value |", "|---|---|",
              f"| routing accuracy | {pct(s['routing_accuracy'])} |",
              f"| tool recall (all expected tools called) | {pct(s['tool_recall'])} |",
              f"| tool precision (called tools that were expected) | {pct(s['tool_precision'])} |",
              f"| trajectory accuracy (expected tools in order) | {pct(s['trajectory_accuracy'])} |",
              f"| SQL execution accuracy, sql questions | {pct(s['sql_execution_accuracy'].get('sql'))} |",
              f"| SQL execution accuracy, hybrid questions | {pct(s['sql_execution_accuracy'].get('hybrid'))} |",
              f"| approval-required actions interrupted | {pct(s['approval_interrupt_rate'])} |",
              f"| invalid actions refused (no approval created) | {pct(s['invalid_action_refused_rate'])} |",
              f"| writes to the schedule without approval | {s['writes_without_approval']} |",
              f"| abstention precision / recall | {pct(a['precision'])} / {pct(a['recall'])} (tp {a['tp']}, fp {a['fp']}, fn {a['fn']}) |",
              f"| citation precision (cited docs that are gold) | {pct(s['citation_precision'])} |",
              f"| citation recall (answers citing a gold doc) | {pct(s['citation_recall'])} |",
              f"| answers with an invented citation number | {pct(s['invalid_citation_rate'])} |",
              f"| answers with sources but no citation | {pct(s['unverified_rate'])} |",
              f"| latency mean / p50 / p95 | {s['latency_s']['mean']:.1f}s / {s['latency_s']['p50']:.1f}s / {s['latency_s']['p95']:.1f}s |",
              f"| tokens per question (prompt / completion) | {s['tokens_per_question']['prompt']:.0f} / {s['tokens_per_question']['completion']:.0f} |",
              f"| LLM calls per question | {s['tokens_per_question']['llm_calls']:.2f} |",
              "", "Keyword correctness (share of required facts found in the answer):", "",
              "| type | score |", "|---|---|"]  # fmt: skip
    lines += [f"| {t} | {pct(v)} |" for t, v in s["keyword_correctness"].items()]
    lines.append("")


def generation_section(lines, name="agent"):
    s = load(f"generation_{name}")
    if not s:
        return
    lines += [f"## Generation (LLM judge on {s['n_graded']} answered questions)", "",
              "Faithful = judge score >= 4 out of 5. Correctness: correct = 1, partial = 0.5, wrong = 0.", "",
              "| type | n | faithfulness (1-5) | faithful rate | correctness | fully correct |",
              "|---|---|---|---|---|---|"]  # fmt: skip
    for t, m in s.items():
        if isinstance(m, dict):
            lines.append(f"| {t} | {m['n']} | {m['faithfulness_mean']} | {pct(m['faithful_rate'])} | "
                         f"{pct(m['correctness'])} | {pct(m['correct_rate'])} |")  # fmt: skip
    lines.append("")


def safety_section(lines):
    s = load("sql_safety")
    if not s:
        return
    d, p = s["direct_sql"], s["agent_prompts"]
    lines += ["## SQL safety", "", "| test | n | result |", "|---|---|---|",
              f"| unsafe queries sent to run_sql | {d['n']} | {d['rejected']} rejected, database unchanged {d['db_unchanged']}/{d['n']} |",
              f"| injection-style chat prompts | {p['n']} | database unchanged {p['db_unchanged']}/{p['n']} |", ""]  # fmt: skip


def main():
    lines = ["# Evaluation results", "",
             f"Generated by `eval/make_report.py` on {date.today()}. Model: `{settings.ollama_model}` "
             "(Ollama, local). Dataset: `eval/datasets/questions_v1.jsonl`. "
             "Protocol: [docs/eval_protocol.md](../docs/eval_protocol.md).", ""]  # fmt: skip
    retrieval_section(lines)
    agent_section(lines)
    generation_section(lines)
    safety_section(lines)
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / "eval_results.md").write_text("\n".join(lines))

    OUT.mkdir(parents=True, exist_ok=True)
    for path in RUNS.glob("*.json*"):
        if path.suffix in (".json", ".jsonl"):
            shutil.copy(path, OUT / path.name)
    print("\n".join(lines))


if __name__ == "__main__":
    main()
