# Architecture

```
 Documents -> Ingestion (parse -> clean -> chunk by sections -> metadata -> embed -> save with version)
                        |
                        v
        Qdrant (vectors + metadata) + BM25 + SQLite (analytics, schedule, approvals)
                        |
 User -> React UI -> FastAPI -> LangGraph agent
                   1. route the question (policy / contract / sql / action / hybrid)
                   2. search (dense + BM25, filters on platform / version) + rerank
                   3. call tools (loop if needed)
                   4. stop and ask for approval before any write action
                   5. answer with citations, or say "I don't know" if evidence is weak

 The MCP server exposes the same tools to external clients.
```

## Packages

| Package | What it does |
|---|---|
| `config` | settings from env variables |
| `ingestion` | read PDF/HTML, clean text, split into chunks, add metadata, handle versions |
| `indexing` | embeddings, Qdrant collection, BM25 index |
| `retrieval` | hybrid search, filters, reranker |
| `llm` | client for Ollama (+ a fake one for tests) |
| `tools` | policy search + version diff, clause search, clause classifier, SQL, compliance check, scheduling |
| `agent` | LangGraph graph: router, tools, approval step, citation check |
| `api` | FastAPI endpoints used by the UI |
| `mcp_server` | MCP server with the same tools |
| `evaluation` | dataset loading, metrics, LLM judge (scripts in `eval/`) |

## Tools

| Tool | Routes | Writes? | What it returns |
|---|---|---|---|
| `search_policies(query, platform?, as_of?)` | policy, hybrid | no | passages with title, section, snapshot date, version |
| `compare_policy_versions(topic, platform?)` | policy, hybrid | no | changed sections between the 2 latest versions |
| `find_clause(clause_type, contract_id?, query?)` | contract, hybrid | no | contract passages (filtered on the contract if given) |
| `classify_clause(text)` | contract, hybrid | no | clause type from the fine-tuned ModernBERT |
| `run_sql(query)` / `explain_schema()` | sql, contract, hybrid, action | no | rows / schema (read-only, allowlist, timeout) |
| `check_post_compliance(caption, platform, is_paid, ...)` | policy, hybrid, action | no | verdict + problems + cited rule passages |
| `create_ticket(title, priority?, reference_type?, reference_id?, link?)` | action, hybrid | tickets only | a task ticket `TCK-...` (internal to-do, no approval needed) |
| `schedule_post(creator, platform, post_datetime, caption, link?, reference?)` | action | approvals + tickets | pending approval + post-request ticket, the graph stops until a human decides |

## Evaluation

`eval/` (datasets + scripts) and `src/creatorops/evaluation/` (metrics, judge). `make eval` runs: dataset
check, retrieval benchmark, full agent run, LLM judge, SQL safety, then writes `reports/eval_results.md`.
Separate: `eval/run_compliance_eval.py`, `eval/ablations.py`, `finetuning/evaluate.py`.
See [eval_protocol.md](eval_protocol.md) and [error_analysis.md](error_analysis.md).

## Rules the code follows

- **Versions:** each document has a `doc_id`. If the same document is ingested again with different content
  (different `content_hash`), a new version is added and the old one gets `is_latest=false`. Old versions are
  kept. Search only uses the latest version unless the question asks for a date or a comparison.
- **SQL:** the SQL tool only runs one `SELECT` on known tables, opens the database read-only and limits rows and time.
- **Write actions:** `schedule_post` is only executed after the user approves it.
- **Citations:** an answer can only cite chunks / clauses / queries that a tool actually returned.

## Chunk metadata

`chunk_id, doc_id, doc_type, platform, title, section_path, page, char_start, char_end, doc_date,
snapshot_date, version, is_latest, source_url, synthetic, content_hash, ingested_at, clause_type`

## API (FastAPI, `make api`)

| Endpoint | What it does |
|---|---|
| `POST /chat` | ask the agent `{question, thread_id?}` -> answer, route, sources, citations, tool calls, usage, latency, or `waiting_approval` with the proposal |
| `GET /approvals?status=pending` | approval queue |
| `POST /approvals/{id}/decision` | approve / reject `{approved, decided_by}`; resumes the waiting chat if there is one |
| `GET /schedule` | scheduled posts (calendar) |
| `POST /sql`, `GET /schema` | read-only SQL panel |
| `POST /search` | hybrid search with filters |
| `GET/POST /tickets`, `GET/PATCH /tickets/{id}` | list, create (task or post request), read, update a ticket |
| `GET /analytics?platform=` | KPIs, monthly series, formats, creators and anomalies for the Analytics page |
| `GET /documents/{doc_id}?version=` | full text of a document version + list of versions, to highlight a cited passage with `char_start` / `char_end` |

## React UI (`app/`, `make ui`)

Vite + React + TypeScript, no UI library. The dev server sends `/api/*` to FastAPI on port 8000.

| File | What it shows |
|---|---|
| `src/api.ts` | fetch helpers + types of the API responses |
| `components/Chat.tsx` | questions, answers, approval cards, sources panel |
| `components/Answer.tsx` | answer text, `[n]` turned into clickable citations (invalid ones crossed out), abstain / unverified warnings |
| `components/SourceCard.tsx` | one source: document passage, SQL query + rows, or policy version diff |
| `components/DocumentViewer.tsx` | full text of the cited version with the passage highlighted (`char_start` / `char_end`) |
| `components/Approvals.tsx` | approval queue with approve / reject |
| `components/Calendar.tsx` | month view of the `schedule` table |
| `components/SqlPanel.tsx` | read-only SQL console + schema |
