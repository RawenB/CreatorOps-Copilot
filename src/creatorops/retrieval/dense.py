"""Dense retrieval: embed the query and search Qdrant."""

from creatorops.config import settings
from creatorops.indexing.embeddings import Embedder
from creatorops.indexing.vectorstore import VectorStore


def open_store(dim: int) -> VectorStore:
    """Open the Qdrant collection configured in settings (local folder or server)."""
    if settings.qdrant_mode == "server":
        return VectorStore(settings.collection_name, dim, url=settings.qdrant_url)
    return VectorStore(settings.collection_name, dim, path=settings.qdrant_path)


class DenseRetriever:
    def __init__(self, embedder=None, store=None):
        self.embedder = embedder or Embedder(settings.embedding_model)
        self.store = store or open_store(self.embedder.dim)

    def search(self, query: str, top_k: int = 10, **filters) -> list[dict]:
        """filters: platform, doc_type, doc_id, as_of, latest_only (see VectorStore.search)."""
        vector = self.embedder.embed_query(query)
        return self.store.search(vector, top_k=top_k, **filters)


def format_citation(chunk: dict) -> str:
    """Short human-readable citation for a chunk."""
    parts = [chunk["title"]]
    if chunk.get("section_path"):
        parts.append(f'section "{chunk["section_path"]}"')
    if chunk.get("snapshot_date"):
        parts.append(f"snapshot {chunk['snapshot_date']} (v{chunk['version']})")
    if chunk.get("synthetic"):
        parts.append("synthetic")
    return ", ".join(parts)
