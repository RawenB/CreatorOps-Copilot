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
| 1 | Setup, corpus + snapshots, synthetic DB, ingestion with versions, dense retrieval | in progress |
| 2 | Hybrid search (BM25 + dense) + reranker, tools (policies, contracts, SQL) | |
| 3 | LangGraph agent (router, approvals, citations), FastAPI | |
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

Commands:

- `make install`: install dependencies
- `make lint` / `make format`: check / fix code style (ruff)
- `make test`: run the tests
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

See [docs/architecture.md](docs/architecture.md) and [docs/decisions.md](docs/decisions.md).
