"""End-to-end ingestion test with a tiny corpus, the fake embedder and local Qdrant."""

import csv

import pytest

from creatorops.indexing.embeddings import FakeEmbedder
from creatorops.indexing.vectorstore import VectorStore
from creatorops.ingestion.pipeline import ingest
from creatorops.ingestion.versioning import Registry
from creatorops.retrieval.dense import DenseRetriever

COLUMNS = [
    "doc_id",
    "title",
    "doc_type",
    "platform",
    "publisher",
    "source_url",
    "retrieved_at",
    "doc_date",
    "snapshot_date",
    "version",
    "license",
    "language",
    "synthetic",
    "num_pages",
    "file_path",
]

OLD_POLICY = "# Branded content\n\n## Disclosure\n\n" + (
    "Creators should add #ad somewhere in the caption of a sponsored post. " * 6
)
NEW_POLICY = "# Branded content\n\n## Disclosure\n\n" + (
    "Creators must turn on the paid partnership label tool for every sponsored post. " * 6
)
CONTRACT = "AGREEMENT\n\n4. Exclusivity\n" + (
    "The creator will not work with any competitor in the beauty category. " * 5
)


def write_manifest(tmp_path, rows):
    with open(tmp_path / "manifest.csv", "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({c: row.get(c, "") for c in COLUMNS})


def policy_row(snapshot, filename):
    return {
        "doc_id": "bc_policy",
        "title": "Branded Content Policy",
        "doc_type": "platform_policy",
        "platform": "instagram",
        "snapshot_date": snapshot,
        "doc_date": snapshot,
        "synthetic": "False",
        "file_path": filename,
    }


@pytest.fixture
def setup(tmp_path):
    (tmp_path / "old.md").write_text(OLD_POLICY)
    (tmp_path / "new.md").write_text(NEW_POLICY)
    (tmp_path / "contract.md").write_text(CONTRACT)
    embedder = FakeEmbedder()
    store = VectorStore("test", embedder.dim, path=tmp_path / "qdrant")
    registry = Registry(tmp_path / "registry.sqlite")
    return tmp_path, embedder, store, registry


def test_versions_and_filters(setup):
    tmp_path, embedder, store, registry = setup
    write_manifest(
        tmp_path,
        [
            policy_row("2024-06-01", "old.md"),
            policy_row("2026-01-01", "new.md"),
            {
                "doc_id": "contract_1",
                "title": "Contract 1",
                "doc_type": "contract",
                "synthetic": "True",
                "file_path": "contract.md",
            },
        ],
    )
    report = ingest(tmp_path / "manifest.csv", tmp_path, registry, store, embedder)
    assert report["new"] == 2 and report["updated"] == 1

    retriever = DenseRetriever(embedder, store)
    query = "sponsored post label"

    latest = retriever.search(query, top_k=5, doc_type="platform_policy")
    assert {r["version"] for r in latest} == {2}

    old = retriever.search(query, top_k=5, doc_type="platform_policy", as_of="2025-01-01")
    assert {r["version"] for r in old} == {1}

    contract = retriever.search("competitor exclusivity", top_k=1, doc_type="contract")[0]
    assert contract["clause_type"] == "exclusivity"
    assert contract["synthetic"] is True


def test_running_twice_changes_nothing(setup):
    tmp_path, embedder, store, registry = setup
    write_manifest(tmp_path, [policy_row("2024-06-01", "old.md")])
    ingest(tmp_path / "manifest.csv", tmp_path, registry, store, embedder)
    count = store.count()

    report = ingest(tmp_path / "manifest.csv", tmp_path, registry, store, embedder)
    assert report["unchanged"] == 1
    assert store.count() == count
