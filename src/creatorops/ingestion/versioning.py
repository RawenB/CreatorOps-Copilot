"""Document versions and chunk store (a small SQLite file).

How updates work:
- every document has a doc_id
- when we ingest a file we compute the sha256 of its parsed text (content_hash)
- same hash as the latest version   -> nothing to do ("unchanged")
- different hash                    -> new version, the old one gets is_latest = 0
  and valid_to = the snapshot date of the new version (history is kept)

The chunks table keeps the text and metadata of every chunk, so the BM25 index and the
evaluation scripts can read chunks without going through the vector store.
"""

import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS documents (
    doc_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    content_hash TEXT NOT NULL,
    snapshot_date TEXT,
    valid_to TEXT,
    is_latest INTEGER NOT NULL,
    ingested_at TEXT NOT NULL,
    PRIMARY KEY (doc_id, version)
);
CREATE TABLE IF NOT EXISTS chunks (
    chunk_id TEXT PRIMARY KEY,
    doc_id TEXT NOT NULL,
    version INTEGER NOT NULL,
    text TEXT NOT NULL,
    metadata TEXT NOT NULL
);
"""


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


class Registry:
    def __init__(self, path: Path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.executescript(SCHEMA)

    def latest(self, doc_id: str):
        """Return (version, content_hash, snapshot_date) of the latest version, or None."""
        return self.conn.execute(
            "SELECT version, content_hash, snapshot_date FROM documents "
            "WHERE doc_id = ? AND is_latest = 1",
            (doc_id,),
        ).fetchone()

    def add_version(self, doc_id: str, text_hash: str, snapshot_date: str | None):
        """Register a document. Returns (status, version, previous_version).

        status is "new" (first time), "updated" (new content) or "unchanged".
        """
        latest = self.latest(doc_id)
        if latest and latest[1] == text_hash:
            return "unchanged", latest[0], None

        now = datetime.now().isoformat(timespec="seconds")
        if latest is None:
            version, previous, status = 1, None, "new"
        else:
            version, previous, status = latest[0] + 1, latest[0], "updated"
            self.conn.execute(
                "UPDATE documents SET is_latest = 0, valid_to = ? WHERE doc_id = ? AND version = ?",
                (snapshot_date, doc_id, previous),
            )
            self.conn.execute(
                "UPDATE chunks SET metadata = json_set(metadata, '$.is_latest', json('false'), "
                "'$.valid_to', ?) WHERE doc_id = ? AND version = ?",
                (snapshot_date, doc_id, previous),
            )
        self.conn.execute(
            "INSERT INTO documents VALUES (?, ?, ?, ?, NULL, 1, ?)",
            (doc_id, version, text_hash, snapshot_date, now),
        )
        self.conn.commit()
        return status, version, previous

    def save_chunks(self, chunks: list[dict]):
        """chunks: list of metadata dicts that contain 'chunk_id' and 'text'."""
        self.conn.executemany(
            "INSERT OR REPLACE INTO chunks VALUES (?, ?, ?, ?, ?)",
            [
                (c["chunk_id"], c["doc_id"], c["version"], c["text"],
                 json.dumps({k: v for k, v in c.items() if k != "text"}))
                for c in chunks
            ],
        )
        self.conn.commit()

    def all_chunks(self, latest_only: bool = False) -> list[dict]:
        rows = self.conn.execute("SELECT text, metadata FROM chunks").fetchall()
        chunks = [{**json.loads(meta), "text": text} for text, meta in rows]
        if latest_only:
            chunks = [c for c in chunks if c["is_latest"]]
        return chunks

    def versions(self, doc_id: str) -> list[tuple]:
        return self.conn.execute(
            "SELECT version, snapshot_date, valid_to, is_latest FROM documents "
            "WHERE doc_id = ? ORDER BY version",
            (doc_id,),
        ).fetchall()
