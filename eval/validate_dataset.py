"""Check the evaluation dataset against the real data before running the eval.

- every gold passage is found in a chunk of one of its gold documents (right version)
- every gold SQL query runs on the analytics database

Run: uv run python eval/validate_dataset.py
"""

import sys
from collections import Counter

from creatorops.evaluation.dataset import check_fields, load_questions
from creatorops.evaluation.metrics import passages_in
from creatorops.tools.common import get_registry
from creatorops.tools.sql import run_sql


def main():
    items = load_questions()
    problems = check_fields(items)

    chunks_by_doc = {}
    for chunk in get_registry().all_chunks():
        chunks_by_doc.setdefault(chunk["doc_id"], []).append(chunk)

    for item in items:
        for doc_id in item["gold_doc_ids"]:
            if doc_id not in chunks_by_doc:
                problems.append(f"{item['id']}: unknown document {doc_id}")
        found = set()
        for doc_id in item["gold_doc_ids"]:
            for chunk in chunks_by_doc.get(doc_id, []):
                found |= passages_in(chunk, item)
        for i, passage in enumerate(item["gold_passages"]):
            if i not in found:
                problems.append(f"{item['id']}: passage not found: {passage!r}")
        if item["gold_sql"]:
            result = run_sql(item["gold_sql"])
            if "error" in result:
                problems.append(f"{item['id']}: gold SQL fails: {result['error']}")

    print(f"{len(items)} questions:", dict(Counter(i["type"] for i in items)))
    for p in problems:
        print("PROBLEM", p)
    print("OK" if not problems else f"{len(problems)} problems")
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
