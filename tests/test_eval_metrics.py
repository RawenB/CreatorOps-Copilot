from collections import Counter

import pytest

from creatorops.evaluation.dataset import check_fields, load_questions
from creatorops.evaluation.metrics import (
    keyword_score,
    precision_recall,
    retrieval_scores,
    sql_result_matches,
    trajectory_ok,
)

ITEM = {"gold_doc_ids": ["faq"], "gold_passages": ["easier to miss", "comments"],
        "gold_version": None}  # fmt: skip


def chunk(doc_id, text, version=1):
    return {"doc_id": doc_id, "text": text, "version": version}


def test_retrieval_scores_perfect_and_partial():
    results = [
        chunk("faq", "A disclosure at the end is EASIER to  miss."),
        chunk("faq", "comments"),
    ]
    scores = retrieval_scores(results, ITEM)
    assert scores["recall@1"] == 0.5
    assert scores["recall@5"] == 1.0
    assert scores["mrr"] == 1.0
    assert scores["ndcg@10"] == pytest.approx(1.0)


def test_retrieval_scores_wrong_document_does_not_count():
    results = [chunk("other", "easier to miss"), chunk("faq", "easier to miss")]
    scores = retrieval_scores(results, ITEM)
    assert scores["recall@1"] == 0.0
    assert scores["mrr"] == 0.5


def test_retrieval_scores_checks_the_version():
    item = {**ITEM, "gold_passages": ["comments"], "gold_version": {"faq": 1}}
    assert retrieval_scores([chunk("faq", "comments", version=2)], item)["recall@10"] == 0.0


def test_sql_result_matches():
    assert sql_result_matches([["Creator F"]], [["Creator F", 310000]])  # extra column ok
    assert sql_result_matches([["a", 1], ["b", 2]], [["b", 2], ["a", 1]])  # order ignored
    assert sql_result_matches([[0.07142]], [[0.0714]])  # rounding
    assert not sql_result_matches([["Creator F"]], [["Creator C"]])
    assert not sql_result_matches([["a"]], [["a"], ["b"]])


def test_keyword_score_with_alternatives():
    assert keyword_score("Contract C003 is not exclusive", ["non-exclusive|not exclusive"]) == 1.0
    assert keyword_score("Posts 166 only", ["166", "168"]) == 0.5
    assert keyword_score(None, ["x"]) == 0.0


def test_trajectory_ok_keeps_order():
    assert trajectory_ok(
        ["explain_schema", "run_sql", "schedule_post"], ["run_sql", "schedule_post"]
    )
    assert not trajectory_ok(["schedule_post", "run_sql"], ["run_sql", "schedule_post"])


def test_precision_recall():
    result = precision_recall([True, True, False], [True, False, True])
    assert result["precision"] == 0.5
    assert result["recall"] == 0.5


def test_dataset_is_valid_and_big_enough():
    items = load_questions()
    assert check_fields(items) == []
    counts = Counter(i["type"] for i in items)
    assert len(items) >= 120
    assert counts["unanswerable"] >= 10 and counts["action"] >= 15
