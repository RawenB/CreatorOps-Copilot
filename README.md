# CreatorOps Copilot

An AI assistant for social-media agencies that manage creators. Account managers ask questions in plain
language, and the assistant answers from three kinds of knowledge:

- **Platform rules**: Instagram, TikTok and YouTube policies, plus FTC and ASA/CAP disclosure rules. Policy pages are stored as **dated, versioned snapshots**.
- **Contracts**: brand deals and talent agreements, searched by clause (exclusivity, term, usage rights, payment…).
- **Performance data**: a synthetic SQLite analytics database of creators, posts, campaigns and metrics.

Every answer cites its sources: a policy section with its snapshot date, a contract clause with its page, or a SQL query with its rows. Write actions, such as scheduling a post, always wait for explicit human approval.

> End-of-course project, AI Engineering (TEK-UP, ING-4-SDIA). All creator and analytics data is **synthetic**. No real client data is used.

## Status

| Phase | Scope | State |
|---|---|---|
| 0 | Scaffold, tooling, CI, config, decisions log | ✅ done |
| 1 | Corpus + snapshots, synthetic DB, ingestion with versioning, dense retrieval CLI | ⏳ next |
| 2 | Hybrid retrieval + reranker, LangGraph agent, tools, citations, FastAPI, first 50 eval questions | ⬜ |
| 3 | MCP server + client demo, approval flow, React UI, compliance checker, 120+ eval, ablations, fine-tuning | ⬜ |
| 4 | Error analysis, final numbers, docs, demo | ⬜ |

This table is updated as each phase lands. No results are reported until they come from a real, logged run.

## Architecture (planned)

```
 Documents ─► Ingestion (parse → clean → structure-aware chunk → metadata → embed → upsert/version)
                        │
                        ▼
        Qdrant (vectors + metadata) + BM25 + SQLite (analytics, schedule)
                        │
 User ► React UI ► FastAPI ► LangGraph agent
                   route → retrieve (hybrid + rerank) → tools → approval interrupt → grounded, cited answer
                                    ▲
                   MCP server exposes the same tools (demo client)
```

Details: [docs/architecture.md](docs/architecture.md). Trade-offs and their reasons: [docs/decisions.md](docs/decisions.md).

## Quickstart

Requirements: [uv](https://docs.astral.sh/uv/) (it installs Python 3.11 automatically), `make`, and later
[Ollama](https://ollama.com/) for the LLM. Docker is optional.

```bash
make install        # create .venv, install pinned deps, install pre-commit hooks
cp .env.example .env
make check          # lint + type-check + tests
```

LLM (local only, from Phase 2 on):

```bash
ollama pull qwen3:8b
```

## Make targets

| Target | What it does |
|---|---|
| `make install` | Sync the pinned environment (`uv.lock`) and install pre-commit hooks |
| `make lint` / `make format` | Ruff lint / auto-format |
| `make typecheck` | mypy (strict) on `src/` |
| `make test` | pytest (fast tests only) |
| `make check` | lint + typecheck + test (what CI runs) |
| `make qdrant-up` | Optional: start a Qdrant server with Docker (local embedded mode is the default) |

Targets for data, ingestion, eval and the UI are added in the phases that introduce them.

## Repository layout

```
src/creatorops/   config, ingestion, indexing, retrieval, agent, tools, llm, api, mcp_server
app/              React web UI (Phase 3)
scripts/          corpus download, policy snapshots, synthetic DB generator
eval/             versioned eval datasets and benchmark scripts
finetuning/       clause-classifier dataset, training, evaluation
tests/            pytest suite
docs/             architecture, decisions, data card, eval protocol, report notes
reports/          results produced by real runs
```

## License

Code: MIT. Third-party documents keep their own licenses. These are recorded per document in `data/manifest.csv`.
