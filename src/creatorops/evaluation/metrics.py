"""Metrics used by the evaluation scripts. Plain functions so they are easy to test."""

import math
import re


def normalize(text: str) -> str:
    """Lowercase, same quotes everywhere, single spaces (so gold passages match chunk text)."""
    text = text.replace("’", "'").replace("‘", "'").replace("“", '"').replace("”", '"')
    return re.sub(r"\s+", " ", text).strip().lower()


# ---------- retrieval ----------


def gold_version_ok(chunk: dict, item: dict) -> bool:
    wanted = (item.get("gold_version") or {}).get(chunk["doc_id"])
    return wanted is None or chunk.get("version") == wanted


def passages_in(chunk: dict, item: dict) -> set[int]:
    """Indexes of the gold passages found in this chunk (empty if it's not a gold chunk)."""
    if chunk["doc_id"] not in item["gold_doc_ids"] or not gold_version_ok(chunk, item):
        return set()
    if not item["gold_passages"]:
        return {0}  # no passage given: any chunk of a gold document counts
    text = normalize(chunk["text"])
    return {i for i, p in enumerate(item["gold_passages"]) if normalize(p) in text}


def retrieval_scores(results: list[dict], item: dict, ks=(1, 5, 10)) -> dict:
    """Recall@k (share of gold passages found in the top k), MRR and nDCG@10."""
    n_gold = max(len(item["gold_passages"]), 1)
    found_per_rank = [passages_in(r, item) for r in results]

    scores = {}
    for k in ks:
        found = set().union(*found_per_rank[:k]) if found_per_rank[:k] else set()
        scores[f"recall@{k}"] = len(found) / n_gold

    first = next((i for i, f in enumerate(found_per_rank) if f), None)
    scores["mrr"] = 0.0 if first is None else 1 / (first + 1)

    # nDCG@10: a result is relevant if it brings a gold passage we did not see yet
    seen, dcg = set(), 0.0
    for i, found in enumerate(found_per_rank[:10]):
        if found - seen:
            dcg += 1 / math.log2(i + 2)
        seen |= found
    ideal = sum(1 / math.log2(i + 2) for i in range(min(n_gold, 10)))
    scores["ndcg@10"] = dcg / ideal
    return scores


# ---------- SQL ----------


def cell(value) -> str:
    if isinstance(value, float):
        return str(round(value, 3))
    return normalize(str(value))


def sql_result_matches(gold_rows: list, pred_rows: list) -> bool:
    """Execution accuracy: same number of rows and every gold row's values are in the predicted row.

    Rows are compared without order, extra predicted columns are allowed
    (e.g. the model also returns the follower count when only the name was asked).
    """
    if len(gold_rows) != len(pred_rows):
        return False
    remaining = [{cell(v) for v in row} for row in pred_rows]
    for row in gold_rows:
        wanted = {cell(v) for v in row}
        match = next((r for r in remaining if wanted <= r), None)
        if match is None:
            return False
        remaining.remove(match)
    return True


# ---------- answers ----------


def keyword_score(answer: str, must_include: list[str]) -> float:
    """Share of the required facts found in the answer. "a|b" means a OR b."""
    if not must_include:
        return 1.0
    text = normalize(answer or "")
    hits = sum(any(normalize(opt) in text for opt in group.split("|")) for group in must_include)
    return hits / len(must_include)


def trajectory_ok(called: list[str], expected: list[str]) -> bool:
    """The expected tools appear in the calls, in the same order (other calls in between are ok)."""
    it = iter(called)
    return all(name in it for name in expected)


def precision_recall(predicted: list[bool], gold: list[bool]) -> dict:
    tp = sum(p and g for p, g in zip(predicted, gold))
    fp = sum(p and not g for p, g in zip(predicted, gold))
    fn = sum(g and not p for p, g in zip(predicted, gold))
    precision = tp / (tp + fp) if tp + fp else 0.0
    recall = tp / (tp + fn) if tp + fn else 0.0
    return {"precision": precision, "recall": recall, "tp": tp, "fp": fp, "fn": fn}


def mean(values) -> float:
    values = list(values)
    return sum(values) / len(values) if values else 0.0


def percentile(values, p: float) -> float:
    values = sorted(values)
    if not values:
        return 0.0
    index = min(len(values) - 1, int(round(p / 100 * (len(values) - 1))))
    return values[index]
