"""LLM judge with a fixed rubric: faithfulness (grounded in the sources) and correctness.

Limitation: the judge is the same local model as the assistant (qwen3:8b), so it can share
its blind spots. That's why a sample is also checked by hand (eval/runs/spot_check.csv).
"""

import json

JUDGE_PROMPT = """You are grading the answer of an assistant for a creator agency.

You get: the QUESTION, a REFERENCE answer written by a human, the SOURCES the assistant
used (document passages or SQL results) and the ANSWER.

Grade two things:

1. faithfulness (1-5): is every claim of the ANSWER supported by the SOURCES?
   5 = every claim is supported
   4 = supported, only small harmless additions
   3 = mostly supported, one claim not in the sources
   2 = several claims not in the sources
   1 = mostly not supported or contradicts the sources
   Judge only against the SOURCES, not your own knowledge.

2. correctness: compare the ANSWER with the REFERENCE.
   "correct" = gives the same key facts (wording can differ, extra correct detail is fine)
   "partial" = some key facts are right, some missing or wrong
   "wrong"   = the key facts are wrong or missing, or it contradicts the reference

Reply with JSON only:
{"faithfulness": <1-5>, "correctness": "correct" | "partial" | "wrong",
 "unsupported_claims": ["..."], "reason": "<one sentence>"}"""

CORRECTNESS_SCORE = {"correct": 1.0, "partial": 0.5, "wrong": 0.0}


def sources_text(row: dict, max_chars: int = 9000) -> str:
    """Cited sources (or all sources if nothing is cited), as text for the judge."""
    sources = row["sources"]
    cited = [s for s in sources if s["n"] in row["citations"]]
    parts = []
    for s in cited or sources:
        if s["kind"] == "document":
            parts.append(
                f"[{s['n']}] {s['doc_id']} v{s['version']} | {s.get('section')}\n{s['text']}"
            )
        elif s["kind"] == "sql":
            parts.append(
                f"[{s['n']}] SQL: {s['query']}\ncolumns: {s['columns']}\nrows: {s['rows'][:30]}"
            )
        else:
            parts.append(
                f"[{s['n']}] policy comparison {s.get('doc_id')}: {json.dumps(s.get('changes'))[:1500]}"
            )
    return "\n\n".join(parts)[:max_chars] or "(no sources)"


def judge(llm, question: str, reference: str, answer: str, sources: str) -> dict:
    user = (f"QUESTION:\n{question}\n\nREFERENCE:\n{reference}\n\nSOURCES:\n{sources}\n\n"
            f"ANSWER:\n{answer}")  # fmt: skip
    response = llm.chat(
        [{"role": "system", "content": JUDGE_PROMPT}, {"role": "user", "content": user}],
        json_mode=True,
    )
    try:
        data = json.loads(response["content"])
        faithfulness = int(data.get("faithfulness", 0))
        correctness = data.get("correctness", "wrong")
        if correctness not in CORRECTNESS_SCORE or not 1 <= faithfulness <= 5:
            raise ValueError
    except (json.JSONDecodeError, ValueError, TypeError):
        return {"faithfulness": None, "correctness": None, "judge_error": response["content"][:300]}
    return {
        "faithfulness": faithfulness,
        "correctness": correctness,
        "unsupported_claims": data.get("unsupported_claims", []),
        "reason": data.get("reason", ""),
    }
