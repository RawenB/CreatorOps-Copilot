"""Qdrant vector store: one point per chunk, all chunk metadata in the payload.

Dates are also stored as integers (20250301) because Qdrant range filters need numbers:
- valid_from_int: date of this version (0 if the document has no date)
- valid_to_int: date of the next version (missing while the version is the latest)
"""

import uuid

from qdrant_client import QdrantClient, models


def date_to_int(d: str | None) -> int:
    return int(d.replace("-", "")) if d else 0


class VectorStore:
    def __init__(self, collection: str, dim: int, path=None, url=None):
        if url:
            self.client = QdrantClient(url=url)
        else:
            self.client = QdrantClient(path=str(path))
        self.collection = collection
        if not self.client.collection_exists(collection):
            self.client.create_collection(
                collection,
                vectors_config=models.VectorParams(size=dim, distance=models.Distance.COSINE),
            )

    @staticmethod
    def point_id(chunk_id: str) -> str:
        return str(uuid.uuid5(uuid.NAMESPACE_URL, chunk_id))

    def upsert(self, chunks: list[dict], vectors) -> None:
        points = []
        for chunk, vector in zip(chunks, vectors):
            payload = dict(chunk)
            payload["valid_from_int"] = date_to_int(chunk.get("valid_from"))
            points.append(
                models.PointStruct(
                    id=self.point_id(chunk["chunk_id"]), vector=list(vector), payload=payload
                )
            )
        for i in range(0, len(points), 256):
            self.client.upsert(self.collection, points=points[i : i + 256])

    def mark_not_latest(self, doc_id: str, version: int, valid_to: str | None) -> None:
        """Called when a newer version of doc_id is ingested."""
        self.client.set_payload(
            self.collection,
            payload={
                "is_latest": False,
                "valid_to": valid_to,
                "valid_to_int": date_to_int(valid_to),
            },
            points=models.Filter(
                must=[
                    models.FieldCondition(key="doc_id", match=models.MatchValue(value=doc_id)),
                    models.FieldCondition(key="version", match=models.MatchValue(value=version)),
                ]
            ),
        )

    def search(
        self,
        vector,
        top_k: int = 10,
        platform: str | None = None,
        doc_type: str | None = None,
        doc_id: str | None = None,
        as_of: str | None = None,
        latest_only: bool = True,
    ) -> list[dict]:
        """Return the top_k chunks as dicts (payload + 'score').

        as_of="2024-01-01" returns the version that was valid on that date instead of the latest.
        """
        query_filter = build_filter(platform, doc_type, doc_id, as_of, latest_only)
        hits = self.client.query_points(
            self.collection, query=list(vector), limit=top_k, query_filter=query_filter
        ).points
        return [{**hit.payload, "score": hit.score} for hit in hits]

    def count(self) -> int:
        return self.client.count(self.collection).count


def build_filter(platform, doc_type, doc_id, as_of, latest_only):
    must = []
    if platform:
        # documents with platform "all" (laws, FTC rules) apply to every platform
        must.append(
            models.FieldCondition(key="platform", match=models.MatchAny(any=[platform, "all"]))
        )
    if doc_type:
        types = [doc_type] if isinstance(doc_type, str) else list(doc_type)
        must.append(models.FieldCondition(key="doc_type", match=models.MatchAny(any=types)))
    if doc_id:
        must.append(models.FieldCondition(key="doc_id", match=models.MatchValue(value=doc_id)))

    if as_of:
        day = date_to_int(as_of)
        must.append(models.FieldCondition(key="valid_from_int", range=models.Range(lte=day)))
        # still valid on that day: no end date yet, or the end date is after the day
        must.append(
            models.Filter(
                should=[
                    models.IsEmptyCondition(is_empty=models.PayloadField(key="valid_to_int")),
                    models.FieldCondition(key="valid_to_int", range=models.Range(gt=day)),
                ]
            )
        )
    elif latest_only:
        must.append(models.FieldCondition(key="is_latest", match=models.MatchValue(value=True)))

    return models.Filter(must=must) if must else None
