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


def comparison_section(lines):
    runs = [(n, load(n)) for n in ("agent_v1", "agent_v2", "holdout_v2")]
    runs = [(n, s) for n, s in runs if s]
    if not runs:
        return
    rows = [
        ("questions", lambda s: str(s["n"])),
        ("routing accuracy", lambda s: pct(s["routing_accuracy"])),
        ("tool recall", lambda s: pct(s["tool_recall"])),
        ("trajectory accuracy", lambda s: pct(s["trajectory_accuracy"])),
        ("SQL execution accuracy (sql)", lambda s: pct(s["sql_execution_accuracy"].get("sql"))),
        ("SQL execution accuracy (hybrid)", lambda s: pct(s["sql_execution_accuracy"].get("hybrid"))),
        ("approval-required actions interrupted", lambda s: pct(s["approval_interrupt_rate"])),
        ("invalid actions refused", lambda s: pct(s["invalid_action_refused_rate"])),
        ("writes without approval", lambda s: str(s["writes_without_approval"])),
        ("abstention precision", lambda s: pct(s["abstention"]["precision"]) if s["abstention"]["tp"] + s["abstention"]["fp"] else "n/a"),
        ("abstention recall", lambda s: pct(s["abstention"]["recall"]) if s["abstention"]["tp"] + s["abstention"]["fn"] else "n/a"),
        ("keyword correctness (all)", lambda s: pct(s["keyword_correctness"].get("all"))),
        ("citation recall", lambda s: pct(s["citation_recall"]) if s["citation_recall"] else "n/a"),
        ("mean latency", lambda s: f"{s['latency_s']['mean']:.1f}s"),
    ]  # fmt: skip
    lines += ["## Agent: v1 vs v2 vs held-out", "",
              "v1 = first full run. v2 = after the two fixes of docs/error_analysis.md (#1, #2). "
              "held-out = 12 new questions written after the fixes, run on v2.", "",
              "| metric | " + " | ".join(n for n, _ in runs) + " |",
              "|---|" + "---|" * len(runs)]  # fmt: skip
    for label, get in rows:
        lines.append(f"| {label} | " + " | ".join(get(s) for _, s in runs) + " |")
    lines.append("")


def spot_check_section(lines):
    path = REPORTS / "eval" / "spot_check_labeled.csv"
    if not path.exists():
        return
    import csv

    rows = list(csv.DictReader(path.open()))
    jf = [int(r["judge_faithfulness"]) >= 4 for r in rows]
    mf = [r["manual_faithful"] == "yes" for r in rows]
    jc = [r["judge_correctness"] == "correct" for r in rows]
    mc = [r["manual_correct"] == "yes" for r in rows]
    n = len(rows)
    lines += ["### Manual spot check of the judge", "",
              f"{n} random answers (seed 42) checked by hand against the gold data and the cited passages "
              "(`reports/eval/spot_check_labeled.csv`).", "",
              "| | judge | manual | agreement |", "|---|---|---|---|",
              f"| faithful | {sum(jf)}/{n} | {sum(mf)}/{n} | {sum(a == b for a, b in zip(jf, mf))}/{n} |",
              f"| fully correct | {sum(jc)}/{n} | {sum(mc)}/{n} | {sum(a == b for a, b in zip(jc, mc))}/{n} |",
              "", "The judge is lenient on citations: read its numbers as an upper bound.", ""]  # fmt: skip


def compliance_section(lines):
    s = load("compliance")
    if not s:
        return
    lines += ["## Compliance checker (60 hand-labelled captions)", "",
              "| method | accuracy | non-compliant precision | recall | F1 | exact reasons | ms / caption |",
              "|---|---|---|---|---|---|---|"]  # fmt: skip
    for method, m in s.items():
        lines.append(f"| {method} | {pct(m['accuracy'])} | {pct(m['non_compliant_precision'])} | "
                     f"{pct(m['non_compliant_recall'])} | {pct(m['non_compliant_f1'])} | "
                     f"{pct(m['reason_exact_match'])} | {max(m['ms_per_caption'], 0.1)} |")  # fmt: skip
    lines.append("")


def ablation_section(lines):
    s = load("ablations")
    if not s:
        return
    lines += ["## Ablations (retrieval)", "",
              "| setting | n | Recall@1 | Recall@5 | Recall@10 | MRR | nDCG@10 |", "|---|---|---|---|---|---|---|"]  # fmt: skip
    for name, m in s.items():
        a = m["all"]
        lines.append(f"| {name} | {a['n']} | {a['recall@1']:.3f} | {a['recall@5']:.3f} | {a['recall@10']:.3f} | "
                     f"{a['mrr']:.3f} | {a['ndcg@10']:.3f} |")  # fmt: skip
    router = load("agent_no_router")
    with_router = load("agent_v2")
    if router and with_router:
        lines += ["", "With vs without the router (agent v2, same questions):", "",
                  "| metric | with router | without router |", "|---|---|---|"]  # fmt: skip
        for label, key in [("tool precision", "tool_precision"), ("trajectory accuracy", "trajectory_accuracy"),
                           ("citation precision", "citation_precision")]:  # fmt: skip
            lines.append(f"| {label} | {pct(with_router[key])} | {pct(router[key])} |")
        lines.append(f"| SQL execution accuracy (sql) | {pct(with_router['sql_execution_accuracy'].get('sql'))} | "
                     f"{pct(router['sql_execution_accuracy'].get('sql'))} |")  # fmt: skip
        lines.append(f"| keyword correctness | {pct(with_router['keyword_correctness']['all'])} | "
                     f"{pct(router['keyword_correctness']['all'])} |")  # fmt: skip
        lines.append(f"| abstention precision / recall | {pct(with_router['abstention']['precision'])} / "
                     f"{pct(with_router['abstention']['recall'])} | {pct(router['abstention']['precision'])} / "
                     f"{pct(router['abstention']['recall'])} |")  # fmt: skip
        lines.append(
            f"| mean latency | {with_router['latency_s']['mean']:.1f}s | {router['latency_s']['mean']:.1f}s |"
        )
        lines.append(f"| prompt tokens / question | {with_router['tokens_per_question']['prompt']:.0f} | "
                     f"{router['tokens_per_question']['prompt']:.0f} |")  # fmt: skip
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
    rows_path = RUNS / "sql_safety.jsonl"
    if rows_path.exists():
        rows = [json.loads(line) for line in rows_path.read_text().splitlines() if line.strip()]
        tried = [r for r in rows if r["kind"] == "agent_prompt"
                 and any(not q.strip().lower().startswith(("select", "with")) for q in r.get("sql_calls", []))]  # fmt: skip
        lines += [f"In {len(tried)} of the chat prompts the model really tried a non-SELECT statement "
                  f"({', '.join(r['id'] for r in tried) or '-'}); the SQL tool rejected it. "
                  "In the others the model refused by itself.", ""]  # fmt: skip


def main():
    lines = ["# Evaluation results", "",
             f"Generated by `eval/make_report.py` on {date.today()}. Model: `{settings.ollama_model}` "
             "(Ollama, local). Dataset: `eval/datasets/questions_v1.jsonl`. "
             "Protocol: [docs/eval_protocol.md](../docs/eval_protocol.md).", ""]  # fmt: skip
    retrieval_section(lines)
    comparison_section(lines)
    agent_section(lines, "agent_v2")
    generation_section(lines, "agent_v2")
    spot_check_section(lines)
    safety_section(lines)
    compliance_section(lines)
    ablation_section(lines)
    lines += ["## Fine-tuning", "", "See [finetuning.md](finetuning.md).", ""]
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / "eval_results.md").write_text("\n".join(lines))

    OUT.mkdir(parents=True, exist_ok=True)
    for path in RUNS.glob("*.json*"):  # summaries + per-question results (not the db copies)
        if path.suffix in (".json", ".jsonl"):
            shutil.copy(path, OUT / path.name)
    print("\n".join(lines))


if __name__ == "__main__":
    main()
