"""Cross-encoder reranker: scores (query, passage) pairs together, more precise than embeddings."""


class Reranker:
    def __init__(self, model_name: str, max_length: int = 512):
        from sentence_transformers import CrossEncoder

        self.model = CrossEncoder(model_name, max_length=max_length)

    def rerank(self, query: str, chunks: list[dict], top_k: int) -> list[dict]:
        if not chunks:
            return []
        scores = self.model.predict([(query, c["text"]) for c in chunks], batch_size=16)
        ranked = sorted(zip(chunks, scores), key=lambda x: x[1], reverse=True)
        return [{**c, "rerank_score": float(s)} for c, s in ranked[:top_k]]
