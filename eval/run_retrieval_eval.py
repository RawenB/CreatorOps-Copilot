"""Retrieval benchmark: Recall@1/5/10, MRR and nDCG@10, overall and by question type.

The question text is searched with the same filters a tool would use:
- policy:   doc_type = platform_policy / regulation / sop, + platform and as_of of the question
- contract: doc_type = contract
- hybrid:   no doc_type filter (the documents can be policies or contracts), + platform
- if the question names a contract (C003, cuad_043) the search is limited to that contract,
  like find_clause(contract_id=...) does. --raw turns this off (question text only).

Run:  uv run python eval/run_retrieval_eval.py                 (hybrid + reranker)
      uv run python eval/run_retrieval_eval.py --mode bm25 --no-rerank
      uv run python eval/run_retrieval_eval.py --raw
"""

import argparse
import json
import re
import time
from pathlib import Path

from creatorops.config import settings
from creatorops.evaluation.dataset import load_questions
from creatorops.evaluation.metrics import mean, retrieval_scores
from creatorops.retrieval.hybrid import HybridRetriever
from creatorops.retrieval.rerank import Reranker
from creatorops.tools.contracts import contract_doc_id
from creatorops.tools.policies import POLICY_TYPES

RUNS = Path("eval/runs")
METRICS = ["recall@1", "recall@5", "recall@10", "mrr", "ndcg@10"]


def filters_for(item: dict, raw: bool = False) -> dict:
    filters = {"platform": item.get("platform"), "as_of": item.get("as_of")}
    if item["type"] == "policy":
        filters["doc_type"] = POLICY_TYPES
    elif item["type"] == "contract":
        filters["doc_type"] = "contract"
    # only one contract named in the question -> search only in it (what find_clause does)
    ids = set(re.findall(r"\b(C\d{3}|cuad_\d{3})\b", item["question"]))
    if not raw and len(ids) == 1 and item["type"] in ("contract", "hybrid"):
        filters["doc_id"] = contract_doc_id(ids.pop())
        filters["doc_type"] = "contract"
    return filters


def summarize(rows: list[dict]) -> dict:
    summary = {"all": {m: round(mean(r[m] for r in rows), 3) for m in METRICS}}
    summary["all"]["n"] = len(rows)
    for t in sorted({r["type"] for r in rows}):
        part = [r for r in rows if r["type"] == t]
        summary[t] = {m: round(mean(r[m] for r in part), 3) for m in METRICS}
        summary[t]["n"] = len(part)
    return summary


def run(mode="hybrid", rerank=True, raw=False, retriever=None, items=None, name=None) -> dict:
    items = items or [i for i in load_questions() if i["gold_doc_ids"]]
    if retriever is None:
        reranker = Reranker(settings.reranker_model) if rerank else None
        retriever = HybridRetriever(reranker=reranker, mode=mode)

    rows, start = [], time.time()
    for item in items:
        results = retriever.search(item["question"], top_k=10, **filters_for(item, raw))
        scores = retrieval_scores(results, item)
        rows.append({"id": item["id"], "type": item["type"], **scores,
                     "retrieved": [f"{r['doc_id']} v{r.get('version')}" for r in results]})  # fmt: skip
    seconds = time.time() - start

    name = name or f"retrieval_{mode}{'_rerank' if rerank else ''}{'_raw' if raw else ''}"
    summary = summarize(rows)
    summary["seconds_per_query"] = round(seconds / len(rows), 3)
    RUNS.mkdir(parents=True, exist_ok=True)
    (RUNS / f"{name}.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    (RUNS / f"{name}_summary.json").write_text(json.dumps(summary, indent=2))
    return summary


def print_table(summary: dict):
    print(f"{'type':<12}{'n':>4}" + "".join(f"{m:>11}" for m in METRICS))
    for t, s in summary.items():
        if isinstance(s, dict):
            print(f"{t:<12}{s['n']:>4}" + "".join(f"{s[m]:>11.3f}" for m in METRICS))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", default="hybrid", choices=["hybrid", "dense", "bm25"])
    parser.add_argument("--no-rerank", action="store_true")
    parser.add_argument("--raw", action="store_true", help="no contract id filter")
    args = parser.parse_args()
    summary = run(args.mode, rerank=not args.no_rerank, raw=args.raw)
    print_table(summary)
    print("seconds per query:", summary["seconds_per_query"])


if __name__ == "__main__":
    main()
