"""Ingestion pipeline: manifest -> parse -> chunk -> metadata -> embed -> store.

Running it twice is safe: unchanged documents are skipped, changed documents get a new
version (see versioning.py).
"""

import csv
from datetime import datetime
from pathlib import Path

from creatorops.ingestion.chunking import fixed_chunks, guess_clause_type, structure_chunks
from creatorops.ingestion.parsers import parse_file
from creatorops.ingestion.versioning import Registry, content_hash

MIN_TEXT_CHARS = 300  # skip empty / broken pages (some archived pages only contain a menu)


def read_manifest(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    # oldest snapshot first, so versions are created in the right order
    return sorted(rows, key=lambda r: (r["doc_id"], r["snapshot_date"] or r["doc_date"]))


def build_chunk_dicts(
    row: dict, text: str, version: int, text_hash: str, chunker: str, context_header=False
):
    """context_header=True puts "title > section" in front of the indexed text (ablation)."""
    chunks = structure_chunks(text) if chunker == "structure" else fixed_chunks(text)
    now = datetime.now().isoformat(timespec="seconds")
    result = []
    for i, c in enumerate(chunks):
        result.append(
            {
                "chunk_id": f"{row['doc_id']}:v{version}:{i}",
                "doc_id": row["doc_id"],
                "doc_type": row["doc_type"],
                "platform": row["platform"] or None,
                "title": row["title"],
                "section_path": c.section_path,
                "page": None,  # our sources are HTML / text, no pages
                "char_start": c.char_start,
                "char_end": c.char_end,
                "doc_date": row["doc_date"] or None,
                "snapshot_date": row["snapshot_date"] or None,
                "version": version,
                "is_latest": True,
                "valid_from": row["snapshot_date"] or row["doc_date"] or None,
                "valid_to": None,
                "source_url": row["source_url"] or None,
                "synthetic": row["synthetic"] == "True",
                "content_hash": text_hash,
                "ingested_at": now,
                "clause_type": guess_clause_type(c.section_path)
                if row["doc_type"] == "contract"
                else None,
                "file_path": row["file_path"],
                "text": f"{row['title']} > {c.section_path}\n{c.text}"
                if context_header
                else c.text,
            }
        )
    return result


def ingest(
    manifest_path,
    data_dir,
    registry: Registry,
    store,
    embedder,
    chunker="structure",
    context_header=False,
):
    """Ingest every file of the manifest. Returns a small report dict."""
    report = {"new": 0, "updated": 0, "unchanged": 0, "skipped": 0, "chunks": 0}
    for row in read_manifest(manifest_path):
        text = parse_file(Path(data_dir) / row["file_path"])
        if len(text) < MIN_TEXT_CHARS:
            print(f"  skip {row['doc_id']} {row['snapshot_date']}: only {len(text)} chars")
            report["skipped"] += 1
            continue

        text_hash = content_hash(text)
        valid_from = row["snapshot_date"] or row["doc_date"] or None
        status, version, previous = registry.add_version(row["doc_id"], text_hash, valid_from)
        report[status] += 1
        if status == "unchanged":
            continue
        if previous is not None:
            store.mark_not_latest(row["doc_id"], previous, valid_from)

        chunks = build_chunk_dicts(row, text, version, text_hash, chunker, context_header)
        vectors = embedder.embed_documents([c["text"] for c in chunks])
        store.upsert(chunks, vectors)
        registry.save_chunks(chunks)
        report["chunks"] += len(chunks)
        print(f"  {status:8s} {row['doc_id']} v{version} ({len(chunks)} chunks)")
    return report
