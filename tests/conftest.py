"""Shared test fixtures: a tiny corpus + synthetic database, no models needed."""

import csv

import pytest

from creatorops.config import settings
from creatorops.indexing.bm25 import BM25Index
from creatorops.indexing.embeddings import FakeEmbedder
from creatorops.indexing.vectorstore import VectorStore
from creatorops.ingestion.pipeline import ingest
from creatorops.ingestion.versioning import Registry
from creatorops.retrieval.dense import DenseRetriever
from creatorops.retrieval.hybrid import HybridRetriever
from creatorops.synthetic_db import create_db
from creatorops.tools import common

FILES = {
    "policy_old.md": "# Branded content\n\n## Disclosure\n\n"
    + "Write #ad somewhere in the caption of a sponsored post. " * 8,
    "policy_new.md": "# Branded content\n\n## Disclosure\n\n"
    + "Turn on the paid partnership label for every sponsored post. " * 8
    + "\n\n## Alcohol\n\nAlcohol branded content must be age restricted to adults. " * 3,
    "contract.md": "AGREEMENT between the parties.\n\n## 4. Exclusivity\n"
    + "The Creator will not promote competitors in the beauty category for 3 months. " * 4
    + "\n\n## 3. Payment\n"
    + "The Brand pays the fee within 30 days of the invoice. " * 4,
}

ROWS = [
    ("bc", "Branded Content Policy", "platform_policy", "instagram", "2024-01-01",
     "policy_old.md"),
    ("bc", "Branded Content Policy", "platform_policy", "instagram", "2026-01-01",
     "policy_new.md"),
    ("contract_x", "Contract X", "contract", "", "", "contract.md"),
]  # fmt: skip


@pytest.fixture
def tiny_corpus(tmp_path, monkeypatch):
    for name, text in FILES.items():
        (tmp_path / name).write_text(text)
    with open(tmp_path / "manifest.csv", "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["doc_id", "title", "doc_type", "platform", "snapshot_date", "doc_date",
                    "source_url", "synthetic", "file_path"])  # fmt: skip
        for doc_id, title, doc_type, platform, snap, path in ROWS:
            w.writerow([doc_id, title, doc_type, platform, snap, snap, "", "False", path])

    embedder = FakeEmbedder()
    store = VectorStore("t", embedder.dim, path=tmp_path / "q")
    registry = Registry(tmp_path / "r.sqlite")
    ingest(tmp_path / "manifest.csv", tmp_path, registry, store, embedder)
    retriever = HybridRetriever(
        dense=DenseRetriever(embedder, store), bm25=BM25Index(registry.all_chunks())
    )
    create_db(tmp_path / "db.sqlite", seed=42)
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    monkeypatch.setattr(settings, "db_path", tmp_path / "db.sqlite")
    common.set_test_objects(retriever, registry)
    yield
    common.set_test_objects(None, None)
