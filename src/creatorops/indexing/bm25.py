"""BM25 keyword index over all chunks (kept in memory, built in a couple of seconds)."""

import re

from rank_bm25 import BM25Okapi

from creatorops.retrieval.filters import matches

STOP_WORDS = set(
    "a an and are as at be by can do does for from has have how i if in is it its me my "
    "of on or our so that the their them then there this to was we what when which who "
    "will with you your".split()
)


def tokenize(text: str) -> list[str]:
    words = re.findall(r"[a-z0-9#]+", text.lower())
    return [w for w in words if w not in STOP_WORDS]


class BM25Index:
    def __init__(self, chunks: list[dict]):
        self.chunks = chunks
        self.bm25 = BM25Okapi([tokenize(c["title"] + " " + c["text"]) for c in chunks])

    def search(self, query: str, top_k: int = 10, **filters) -> list[dict]:
        scores = self.bm25.get_scores(tokenize(query))
        order = scores.argsort()[::-1]
        results = []
        for i in order:
            if scores[i] <= 0:
                break
            chunk = self.chunks[i]
            if matches(chunk, **filters):
                results.append({**chunk, "score": float(scores[i])})
                if len(results) == top_k:
                    break
        return results
