"""Compliance checker benchmark on 60 hand-labelled captions.

Methods:
  rules  check_post_compliance (deterministic rules + cited passages)
  llm    the local LLM gets the same rule passages and the caption, and answers with a verdict

Metrics: verdict accuracy, precision / recall / F1 for "non_compliant" (the class we must catch),
and reason accuracy (the predicted rules = the labelled rules, only for non-compliant captions).

Run: uv run python eval/run_compliance_eval.py --methods rules,llm
"""

import argparse
import json
import time
from pathlib import Path

from creatorops.evaluation.metrics import mean, precision_recall
from creatorops.tools.compliance import MESSAGES, RULES, check_post_compliance, find_passage

DATASET = Path("eval/datasets/compliance_captions.jsonl")
RUNS = Path("eval/runs")

LLM_PROMPT = """You check social media captions for a creator agency before they are posted.
Rules (from the agency SOP, the FTC and the platform policies):
{rules}

Rule ids you can use: {rule_ids}

Reply with JSON only:
{{"verdict": "compliant" | "non_compliant", "problems": ["<rule id>", ...]}}"""


def rules_text() -> str:
    lines = []
    for rule, (doc_id, quote) in RULES.items():
        passage = find_passage(doc_id, quote)
        lines.append(
            f'- {rule}: {MESSAGES[rule]} (source {doc_id}: "{quote}")'
            if passage
            else f"- {rule}: {MESSAGES[rule]}"
        )
    return "\n".join(lines)


def run_llm(items):
    from creatorops.llm.client import get_llm

    llm = get_llm()
    system = LLM_PROMPT.format(rules=rules_text(), rule_ids=", ".join(RULES))
    preds = []
    for item in items:
        post = {k: item[k] for k in ("caption", "platform", "is_paid", "paid_label_on", "brand_category",
                                     "age_restricted")}  # fmt: skip
        response = llm.chat([{"role": "system", "content": system},
                             {"role": "user", "content": json.dumps(post, ensure_ascii=False)}],
                            json_mode=True)  # fmt: skip
        try:
            data = json.loads(response["content"])
            preds.append(
                {
                    "verdict": data.get("verdict"),
                    "problems": [p for p in data.get("problems", []) if p in RULES],
                }
            )
        except (json.JSONDecodeError, AttributeError):
            preds.append({"verdict": None, "problems": []})
    return preds


def run_rules(items):
    preds = []
    for item in items:
        result = check_post_compliance(item["caption"], item["platform"], item["is_paid"], item["paid_label_on"],
                                       item["brand_category"], item["age_restricted"], with_sources=False)  # fmt: skip
        preds.append(
            {"verdict": result["verdict"], "problems": [p["rule"] for p in result["problems"]]}
        )
    return preds


def score(items, preds, seconds):
    gold = [i["label"] == "non_compliant" for i in items]
    pred = [p["verdict"] == "non_compliant" for p in preds]
    pr = precision_recall(pred, gold)
    f1 = 2 * pr["precision"] * pr["recall"] / (pr["precision"] + pr["recall"]) if pr["tp"] else 0.0
    bad = [(i, p) for i, p in zip(items, preds) if i["label"] == "non_compliant"]
    return {
        "n": len(items),
        "accuracy": round(mean(i["label"] == p["verdict"] for i, p in zip(items, preds)), 3),
        "non_compliant_precision": round(pr["precision"], 3),
        "non_compliant_recall": round(pr["recall"], 3),
        "non_compliant_f1": round(f1, 3),
        "reason_exact_match": round(
            mean(set(i["reasons"]) == set(p["problems"]) for i, p in bad), 3
        ),
        "ms_per_caption": round(1000 * seconds / len(items), 1),
        "errors": [
            {
                "id": i["id"],
                "caption": i["caption"],
                "gold": i["label"],
                "gold_reasons": i["reasons"],
                "pred": p["verdict"],
                "pred_reasons": p["problems"],
                "note": i["note"],
            }
            for i, p in zip(items, preds)
            if i["label"] != p["verdict"]
        ],  # fmt: skip
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--methods", default="rules,llm")
    args = parser.parse_args()
    items = [json.loads(line) for line in DATASET.read_text().splitlines()]
    summary = {}
    for method in args.methods.split(","):
        start = time.time()
        preds = run_rules(items) if method == "rules" else run_llm(items)
        summary[method] = score(items, preds, time.time() - start)
        s = summary[method]
        print(f"{method}: accuracy {s['accuracy']}, non-compliant P/R/F1 {s['non_compliant_precision']}/"
              f"{s['non_compliant_recall']}/{s['non_compliant_f1']}, reasons {s['reason_exact_match']}")  # fmt: skip
        for e in s["errors"]:
            print(
                "   wrong:",
                e["id"],
                e["gold"],
                "->",
                e["pred"],
                e["pred_reasons"],
                "|",
                e["caption"][:60],
            )
    RUNS.mkdir(parents=True, exist_ok=True)
    (RUNS / "compliance_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
