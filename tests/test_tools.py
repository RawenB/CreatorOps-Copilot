"""Policy and contract tools on a tiny corpus (fake embedder, no models)."""

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
from creatorops.tools import common
from creatorops.tools.contracts import find_clause
from creatorops.tools.policies import compare_policy_versions, search_policies

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


@pytest.fixture(autouse=True)
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
    monkeypatch.setattr(settings, "data_dir", tmp_path)
    common.set_test_objects(retriever, registry)
    yield
    common.set_test_objects(None, None)


def test_search_policies_returns_latest_rules_with_citation_fields():
    result = search_policies("paid partnership label", platform="instagram", top_k=3)
    sources = result["sources"]
    assert sources and all(s["doc_type"] != "contract" for s in sources)
    assert all(s["version"] == 2 for s in sources)
    assert {"source_id", "title", "section", "snapshot_date", "text"} <= sources[0].keys()


def test_search_policies_as_of_returns_old_rules():
    result = search_policies("sponsored post caption", as_of="2025-01-01")
    assert {s["version"] for s in result["sources"]} == {1}


def test_compare_policy_versions_finds_changed_and_added_sections():
    result = compare_policy_versions("disclosure", doc_id="bc")
    assert result["old_version"]["snapshot_date"] == "2024-01-01"
    changes = {c["section"]: c["change"] for c in result["changes"]}
    assert changes["Branded content > Disclosure"] == "modified"
    assert changes["Branded content > Alcohol"] == "added"


def test_compare_with_single_version_says_so():
    assert "error" in compare_policy_versions("exclusivity", doc_id="contract_x")


def test_find_clause_puts_matching_clause_type_first():
    result = find_clause("exclusivity", contract_id="contract_x", top_k=2)
    assert result["sources"][0]["clause_type"] == "exclusivity"


def test_find_clause_rejects_unknown_type():
    assert "error" in find_clause("pizza")
