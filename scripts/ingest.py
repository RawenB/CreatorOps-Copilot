"""Ingest the corpus listed in data/manifest.csv into Qdrant + the chunk registry.

Usage: uv run python scripts/ingest.py
Run it again after re-downloading: only new or changed documents are processed.
"""

import time

from creatorops.config import settings
from creatorops.indexing.embeddings import Embedder
from creatorops.ingestion.pipeline import ingest
from creatorops.ingestion.versioning import Registry
from creatorops.retrieval.dense import open_store

start = time.time()
embedder = Embedder(settings.embedding_model)
store = open_store(embedder.dim)
registry = Registry(settings.data_dir / "processed" / "registry.sqlite")

report = ingest(settings.manifest_path, settings.data_dir, registry, store, embedder)

print(report)
print(f"points in Qdrant: {store.count()}, took {time.time() - start:.0f}s")
