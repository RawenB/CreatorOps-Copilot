"""Hybrid retrieval: dense + BM25 merged with Reciprocal Rank Fusion, then optional reranking.

mode="dense" / "bm25" / "hybrid" is used by the ablation study to compare the three.
"""

from creatorops.config import settings
from creatorops.indexing.bm25 import BM25Index
from creatorops.ingestion.versioning import Registry
from creatorops.retrieval.dense import DenseRetriever

RRF_K = 60  # standard value from the RRF paper
CANDIDATES = 30  # how many results we take from each retriever before fusing / reranking


def rrf_fuse(result_lists: list[list[dict]], k: int = RRF_K) -> list[dict]:
    """Reciprocal Rank Fusion: score = sum over lists of 1 / (k + rank)."""
    scores = {}
    chunks = {}
    for results in result_lists:
        for rank, chunk in enumerate(results, start=1):
            cid = chunk["chunk_id"]
            scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank)
            chunks.setdefault(cid, chunk)
    ordered = sorted(scores, key=scores.get, reverse=True)
    return [{**chunks[cid], "score": scores[cid]} for cid in ordered]


class HybridRetriever:
    def __init__(self, dense=None, bm25=None, reranker=None, mode: str = "hybrid"):
        self.dense = dense or DenseRetriever()
        if bm25 is None:
            registry = Registry(settings.data_dir / "processed" / "registry.sqlite")
            bm25 = BM25Index(registry.all_chunks())
        self.bm25 = bm25
        self.reranker = reranker
        self.mode = mode

    def search(self, query: str, top_k: int = 10, **filters) -> list[dict]:
        n = CANDIDATES if (self.reranker or self.mode == "hybrid") else top_k
        if self.mode == "dense":
            results = self.dense.search(query, top_k=n, **filters)
        elif self.mode == "bm25":
            results = self.bm25.search(query, top_k=n, **filters)
        else:
            results = rrf_fuse(
                [
                    self.dense.search(query, top_k=n, **filters),
                    self.bm25.search(query, top_k=n, **filters),
                ]
            )
        if self.reranker:
            return self.reranker.rerank(query, results[:CANDIDATES], top_k)
        return results[:top_k]
