# Architecture

> Status: **planned design** (Phase 0). Each section is updated when its component is implemented.
> Trade-offs are explained in [decisions.md](decisions.md).

## Overview

```
 Documents ─► Ingestion (parse → clean → structure-aware chunk → metadata → embed → upsert/version)
                        │
                        ▼
        Qdrant (vectors + payload metadata) + BM25 index + SQLite (analytics, schedule, approvals)
                        │
 User ► React UI ► FastAPI ► LangGraph agent ──────────────────────────────┐
                   1. route intent (policy | contract | sql | action | hybrid)
                   2. hybrid retrieval (dense + BM25, metadata filters) + rerank
                   3. tool loop
                   4. human-approval interrupt before any write
                   5. grounded answer + citation verification + abstention
                                                                          │
                          MCP server exposes the same tools ◄─────────────┘
```

## Components

| Package | Responsibility | Phase |
|---|---|---|
| `creatorops.config` | Typed settings from `CREATOROPS_*` env vars | 0 ✅ |
| `creatorops.ingestion` | Parse PDF/HTML, clean, structure-aware chunking, chunk metadata, content-hash versioning | 1 |
| `creatorops.indexing` | Embeddings, Qdrant collection, BM25 index | 1–2 |
| `creatorops.retrieval` | Hybrid fusion, metadata filters (`is_latest`, platform, `as_of`), reranker | 1–2 |
| `creatorops.llm` | `LLMClient` interface; `ollama` and `fake` providers | 2 |
| `creatorops.tools` | Plain typed functions: policies, contracts, SQL, compliance, scheduling | 2–3 |
| `creatorops.agent` | LangGraph graph: router, tool loop, approval interrupt, citation verification | 2–3 |
| `creatorops.api` | FastAPI endpoints for chat, sources, SQL, approvals, schedule | 2 |
| `creatorops.mcp_server` | Same tools exposed through the official MCP Python SDK | 3 |
| `app/` | React + TypeScript UI | 3 |

## Key invariants

- **Versioning:** a document is identified by `doc_id`. Re-ingesting with a different `content_hash` creates a new `version` and sets `is_latest=false` on the previous one. History is kept. Retrieval filters on `is_latest=true` unless the query asks for a date (`as_of`) or a comparison.
- **SQL safety:** `run_sql` accepts a single `SELECT` on allowlisted tables, opens the database read-only, and enforces a row limit and a timeout.
- **Write actions:** the only write tool (`schedule_post`) is reached through a LangGraph interrupt, and no row is written without an explicit approval record.
- **Citations:** each claim in an answer cites a chunk, clause or query that was actually returned by a tool in that run. Citations are verified before the answer is returned. If the evidence is too weak, the agent abstains.

## Chunk metadata

`chunk_id, doc_id, doc_type, platform, title, section_path, page, char_start, char_end, doc_date, snapshot_date,
version, is_latest, source_url, synthetic, content_hash, ingested_at, clause_type (nullable)`
