"""Generation benchmark with the LLM judge, on the answers of an agent run.

For every policy / contract / sql / hybrid question the agent answered (did not abstain):
faithfulness (1-5, grounded in the cited sources) and correctness vs the reference answer.
Also writes a random sample to eval/runs/spot_check.csv for a manual check.

Run (after run_agent_eval.py):  uv run python eval/run_generation_eval.py --run agent
"""

import argparse
import csv
import json
import random
from pathlib import Path

from creatorops.evaluation.dataset import load_questions
from creatorops.evaluation.judge import CORRECTNESS_SCORE, judge, sources_text
from creatorops.evaluation.metrics import mean
from creatorops.llm.client import get_llm

RUNS = Path("eval/runs")
TYPES = ("policy", "contract", "sql", "hybrid")


def summarize(rows: list[dict]) -> dict:
    graded = [r for r in rows if r.get("faithfulness")]
    summary = {"n_answered": len(rows), "n_graded": len(graded)}
    for t in TYPES + ("all",):
        part = [r for r in graded if t == "all" or r["type"] == t]
        if not part:
            continue
        summary[t] = {
            "n": len(part),
            "faithfulness_mean": round(mean(r["faithfulness"] for r in part), 2),
            "faithful_rate": round(mean(r["faithfulness"] >= 4 for r in part), 3),
            "correctness": round(mean(CORRECTNESS_SCORE[r["correctness"]] for r in part), 3),
            "correct_rate": round(mean(r["correctness"] == "correct" for r in part), 3),
        }
    return summary


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run", default="agent", help="name of the agent run in eval/runs")
    parser.add_argument("--sample", type=int, default=20)
    args = parser.parse_args()

    items = {i["id"]: i for i in load_questions()}
    rows = [json.loads(line) for line in (RUNS / f"{args.run}.jsonl").read_text().splitlines()]
    rows = [r for r in rows if r["type"] in TYPES and r["answer"] and not r["abstained"]]

    llm = get_llm()
    for i, row in enumerate(rows, 1):
        item = items[row["id"]]
        row.update(judge(llm, item["question"], item["reference_answer"], row["answer"],
                         sources_text(row)))  # fmt: skip
        print(f"[{i}/{len(rows)}] {row['id']} faithfulness={row['faithfulness']} "
              f"correctness={row['correctness']}", flush=True)  # fmt: skip

    out = RUNS / f"generation_{args.run}"
    Path(f"{out}.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows))
    summary = summarize(rows)
    Path(f"{out}_summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))

    # sample for the manual check (fill the two manual_ columns by hand)
    random.seed(42)
    sample = random.sample(rows, min(args.sample, len(rows)))
    with open(RUNS / "spot_check.csv", "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "question", "reference", "answer", "judge_faithfulness",
                         "judge_correctness", "manual_faithful", "manual_correct", "notes"])  # fmt: skip
        for r in sample:
            writer.writerow([r["id"], items[r["id"]]["question"], items[r["id"]]["reference_answer"],
                             r["answer"], r["faithfulness"], r["correctness"], "", "", ""])  # fmt: skip


if __name__ == "__main__":
    main()
