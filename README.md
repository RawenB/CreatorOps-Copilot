# CreatorOps Copilot

An assistant for social-media agencies that manage creators. An account manager asks a question and the
assistant answers using:

- **platform rules** (Instagram, TikTok, YouTube + FTC / ASA disclosure rules), stored as dated snapshots
- **contracts** (brand deals, talent agreements), searched by clause type
- **performance data** in a SQLite database (synthetic creators, posts, campaigns, metrics)

Answers come with citations (policy section + snapshot date, contract clause, or SQL query + rows).
Actions like scheduling a post need a human approval first.

End-of-course project, AI Engineering (TEK-UP, ING-4-SDIA). All creator and analytics data is synthetic.

## Plan (1 week)

| Day | Work | Status |
|---|---|---|
| 1 | Setup, corpus + snapshots, synthetic DB, ingestion with versions, dense retrieval | done |
| 2 | Hybrid search (BM25 + dense) + reranker, tools (policies, contracts, SQL) | done |
| 3 | LangGraph agent (router, approvals, citations), FastAPI | done |
| 4 | MCP server + client demo, React UI | |
| 5 | Eval set (120+ questions), retrieval / generation / SQL / agent metrics | |
| 6 | Fine-tuning (clause classifier on Colab), ablations, compliance checker | |
| 7 | Error analysis, report notes, demo | |

## Setup

You need [uv](https://docs.astral.sh/uv/), [Ollama](https://ollama.com/) and optionally Docker.

```bash
make install
cp .env.example .env
ollama pull qwen3:8b
make test
```

Build the data and the index (takes a few minutes the first time):

```bash
make db        # synthetic SQLite database
make corpus    # download policies, regulations, CUAD contracts + build synthetic documents
make ingest    # parse, chunk, embed and store in Qdrant (re-run = only changed documents)
uv run python scripts/search.py "do I need to label a paid partnership?" --platform instagram
uv run python scripts/search.py "branded content rules" --platform tiktok --as-of 2024-01-01
```

Ask the agent (needs Ollama running):

```bash
uv run python scripts/ask.py "Is contract C003 exclusive, and what are its payment terms?"
uv run python scripts/ask.py "Schedule a post for Creator D on Instagram on 2026-12-04 at 18:00"  # asks for approval
make api   # FastAPI on http://localhost:8000 (docs at /docs)
```

Commands:

- `make install`: install dependencies
- `make lint` / `make format`: check / fix code style (ruff)
- `make test`: run the tests
- `make db` / `make corpus` / `make ingest`: build the data and the search index
- `make api`: start the FastAPI backend
- `make mcp`: start the MCP server (stdio), see [docs/mcp.md](docs/mcp.md) for the Claude Desktop config
- `make qdrant`: start a Qdrant server with Docker (optional, by default Qdrant runs locally without a server)

## Project structure

```
src/creatorops/   python package (ingestion, indexing, retrieval, agent, tools, llm, api, mcp_server)
app/              React UI
scripts/          download the corpus, generate the synthetic database
eval/             evaluation questions and scripts
finetuning/       clause classifier training
tests/            tests
docs/             architecture and decisions
reports/          results
```

See [docs/architecture.md](docs/architecture.md), [docs/decisions.md](docs/decisions.md) and [docs/mcp.md](docs/mcp.md).
