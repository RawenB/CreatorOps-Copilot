from creatorops.indexing.bm25 import BM25Index, tokenize
from creatorops.retrieval.filters import matches
from creatorops.retrieval.hybrid import HybridRetriever, rrf_fuse


def chunk(cid, text, **meta):
    base = {"chunk_id": cid, "title": "", "text": text, "is_latest": True, "platform": "instagram"}
    return {**base, **meta}


CHUNKS = [
    chunk("a", "Use the paid partnership label for branded content"),
    chunk("b", "Alcohol ads must target people of legal drinking age"),
    chunk(
        "c",
        "Old rule: write #ad in the caption",
        is_latest=False,
        valid_from="2023-01-01",
        valid_to="2025-01-01",
    ),
    chunk("d", "TikTok branded content toggle", platform="tiktok"),
]


def test_tokenize_removes_stop_words_and_keeps_hashtags():
    assert tokenize("What is the #ad rule?") == ["#ad", "rule"]


def test_bm25_finds_keyword_match():
    index = BM25Index(CHUNKS)
    assert index.search("alcohol drinking age", top_k=1)[0]["chunk_id"] == "b"


def test_bm25_respects_latest_and_platform_filters():
    index = BM25Index(CHUNKS)
    ids = [r["chunk_id"] for r in index.search("branded content #ad caption", top_k=5)]
    assert "c" not in ids  # old version hidden by default
    ids = [r["chunk_id"] for r in index.search("branded content", top_k=5, platform="instagram")]
    assert "d" not in ids


def test_as_of_filter_picks_old_version():
    assert matches(CHUNKS[2], as_of="2024-06-01")
    assert not matches(CHUNKS[2], as_of="2025-06-01")


def test_rrf_rewards_documents_found_by_both():
    dense = [{"chunk_id": "x"}, {"chunk_id": "y"}]
    bm25 = [{"chunk_id": "y"}, {"chunk_id": "z"}]
    assert rrf_fuse([dense, bm25])[0]["chunk_id"] == "y"


class FakeDense:
    def search(self, query, top_k=10, **filters):
        return [CHUNKS[0], CHUNKS[1]][:top_k]


def test_hybrid_modes():
    bm25 = BM25Index(CHUNKS)
    hybrid = HybridRetriever(dense=FakeDense(), bm25=bm25, mode="hybrid")
    top = hybrid.search("alcohol drinking age", top_k=2)
    assert {r["chunk_id"] for r in top} == {"a", "b"}
    assert top[0]["chunk_id"] == "b"  # found by both retrievers
    only_bm25 = HybridRetriever(dense=FakeDense(), bm25=bm25, mode="bm25")
    assert only_bm25.search("alcohol", top_k=1)[0]["chunk_id"] == "b"
