"""Load and check the evaluation dataset (eval/datasets/*.jsonl)."""

import json
from pathlib import Path

DATASET = Path("eval/datasets/questions_v1.jsonl")
TYPES = ["policy", "contract", "sql", "hybrid", "action", "unanswerable"]
REQUIRED = ["id", "question", "type", "gold_doc_ids", "gold_passages", "gold_sql",
            "expected_tools", "reference_answer"]  # fmt: skip


def load_questions(path=DATASET, types=None, limit=None) -> list[dict]:
    items = [json.loads(line) for line in Path(path).read_text().splitlines() if line.strip()]
    if types:
        items = [i for i in items if i["type"] in types]
    return items[:limit] if limit else items


def check_fields(items: list[dict]) -> list[str]:
    """Problems that don't need the data (missing fields, unknown types, duplicate ids)."""
    problems = []
    seen = set()
    for item in items:
        for field in REQUIRED:
            if field not in item:
                problems.append(f"{item.get('id')}: missing field {field}")
        if item.get("type") not in TYPES:
            problems.append(f"{item.get('id')}: unknown type {item.get('type')}")
        if item.get("id") in seen:
            problems.append(f"{item['id']}: duplicate id")
        seen.add(item.get("id"))
        if item.get("gold_passages") and not item.get("gold_doc_ids"):
            problems.append(f"{item['id']}: gold passages without gold documents")
    return problems
