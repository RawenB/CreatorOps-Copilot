"""Text embeddings.

Embedder uses a sentence-transformers model (BGE by default).
FakeEmbedder is a tiny hashing bag-of-words embedder used in tests (no model download).
"""

import hashlib

import numpy as np

# BGE v1.5 English models work better when queries start with this instruction
BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


class Embedder:
    def __init__(self, model_name: str):
        from sentence_transformers import SentenceTransformer  # slow import, only when needed

        self.model_name = model_name
        self.model = SentenceTransformer(model_name)
        self.dim = self.model.get_embedding_dimension()

    def embed_documents(self, texts: list[str], batch_size: int = 32) -> np.ndarray:
        return self.model.encode(
            texts,
            batch_size=batch_size,
            normalize_embeddings=True,
            show_progress_bar=len(texts) > 200,
        )

    def embed_query(self, query: str) -> np.ndarray:
        if "bge" in self.model_name and "en" in self.model_name:
            query = BGE_QUERY_PREFIX + query
        return self.model.encode([query], normalize_embeddings=True)[0]


class FakeEmbedder:
    """Hashes words into a fixed-size vector. Good enough for tests."""

    def __init__(self, dim: int = 64):
        self.dim = dim

    def _embed(self, text: str) -> np.ndarray:
        vec = np.zeros(self.dim)
        for word in text.lower().split():
            h = int(hashlib.md5(word.strip(".,:;!?").encode()).hexdigest(), 16)
            vec[h % self.dim] += 1
        norm = np.linalg.norm(vec)
        return vec / norm if norm else vec

    def embed_documents(self, texts: list[str], batch_size: int = 32) -> np.ndarray:
        return np.array([self._embed(t) for t in texts])

    def embed_query(self, query: str) -> np.ndarray:
        return self._embed(query)
