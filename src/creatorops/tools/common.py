"""Shared objects for the tools (loaded once, the models are slow to load)."""

from creatorops.config import settings
from creatorops.ingestion.versioning import Registry

_retriever = None
_registry = None


def get_retriever():
    global _retriever
    if _retriever is None:
        from creatorops.retrieval.hybrid import HybridRetriever
        from creatorops.retrieval.rerank import Reranker

        reranker = Reranker(settings.reranker_model) if settings.use_reranker else None
        _retriever = HybridRetriever(reranker=reranker)
    return _retriever


def get_registry() -> Registry:
    global _registry
    if _registry is None:
        _registry = Registry(settings.data_dir / "processed" / "registry.sqlite")
    return _registry


def set_test_objects(retriever=None, registry=None):
    """Used by tests to plug in small fake objects."""
    global _retriever, _registry
    _retriever = retriever
    _registry = registry


def to_source(chunk: dict) -> dict:
    """What a tool returns for each retrieved passage: the text + everything needed to cite it."""
    return {
        "source_id": chunk["chunk_id"],
        "doc_id": chunk["doc_id"],
        "title": chunk["title"],
        "doc_type": chunk["doc_type"],
        "platform": chunk.get("platform"),
        "section": chunk.get("section_path") or None,
        "snapshot_date": chunk.get("snapshot_date"),
        "version": chunk.get("version"),
        "is_latest": chunk.get("is_latest"),
        "source_url": chunk.get("source_url"),
        "synthetic": chunk.get("synthetic", False),
        "clause_type": chunk.get("clause_type"),
        "char_start": chunk.get("char_start"),
        "char_end": chunk.get("char_end"),
        "score": round(float(chunk.get("rerank_score", chunk.get("score", 0.0))), 4),
        "text": chunk["text"],
    }
