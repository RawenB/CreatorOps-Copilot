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
| 4 | MCP server + client demo, React UI | done |
| 5 | Eval set (120+ questions), retrieval / generation / SQL / agent metrics | done |
| 6 | Fine-tuning (clause classifier), ablations, compliance checker | done |
| 7 | Error analysis, report notes, demo | done |

## Results

Full tables: [reports/eval_results.md](reports/eval_results.md), [reports/finetuning.md](reports/finetuning.md),
failures: [docs/error_analysis.md](docs/error_analysis.md), protocol: [docs/eval_protocol.md](docs/eval_protocol.md).

| | |
|---|---|
| Retrieval (hybrid + reranker, 85 questions) | Recall@10 0.824, MRR 0.658 |
| Version-aware retrieval on old-version questions | Recall@10 1.00 (latest-only: 0.00) |
| Agent routing accuracy | 96% |
| SQL execution accuracy | 59% (75% on held-out questions) |
| Answers judged faithful / correct (LLM judge) | 80% / 76% (manual check: judge is optimistic) |
| Writes without human approval | 0 |
| Unsafe SQL rejected | 18/18, injection prompts: database unchanged 10/10 |
| Compliance checker (60 captions) | 88% accuracy, 100% of non-compliant captions caught |
| Clause classifier (fine-tuned ModernBERT vs qwen3:8b zero-shot) | macro-F1 0.84 vs 0.74, 17 ms vs 576 ms |

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

Web UI (needs Node 20+ and `make api` running in another terminal):

```bash
make ui    # React app on http://localhost:5173
```

The UI has 6 pages:

- **Chat**: answers with clickable citations; the sources panel shows the passage highlighted in the stored
  document (any stored version), the SQL query + rows, the policy diff, the compliance verdict or the ticket
  the assistant created.
- **Tickets**: tasks (open / in progress / done) and post requests, each with an id (`TCK-0007`), a link
  (draft, brief, asset) and a checked reference (contract `C003`, campaign, post, creator or policy
  document, which opens in the viewer). A ticket can be shared with its URL (`/#/tickets/7`). Tickets are
  also created automatically: every scheduling request (from the chat, the form or an MCP client) opens a
  post-request ticket, the assistant can create tasks ("create a ticket to fix post 166"), and the Analytics
  page proposes a ticket for every anomaly.
- **Approvals**: approve or reject scheduling requests (nothing is scheduled before).
- **Analytics**: KPIs, reach / engagement by month, engagement by format, creators table, and "things to
  check" found automatically (undisclosed paid posts, likes rising much more than reach, viral posts, reach
  drops). The data is **synthetic** (see below).
- **Calendar**: scheduled posts by month. **SQL**: read-only console with examples and the schema.

**Where the analytics come from:** `scripts/generate_analytics_db.py` generates the SQLite database
(8 fictional creators, 1,418 posts from May to October 2026, daily metrics, campaigns, contracts index)
with a fixed seed, including a few planted problems to find. Real metrics would come from the Instagram
Graph API / TikTok / YouTube business APIs (a Meta business account and app review are needed), which is
out of scope for this project; the database schema is the same one such an import would fill.

Commands:

- `make install`: install dependencies
- `make lint` / `make format`: check / fix code style (ruff)
- `make test`: run the tests
- `make db` / `make corpus` / `make ingest`: build the data and the search index
- `make api`: start the FastAPI backend
- `make ui`: start the React UI (Vite dev server)
- `make mcp`: start the MCP server (stdio), see [docs/mcp.md](docs/mcp.md) for the Claude Desktop config
- `make eval`: full evaluation (~1 h, needs Ollama), then `reports/eval_results.md`; `make eval-retrieval` (~2 min)
- `uv run python eval/run_compliance_eval.py`, `uv run python eval/ablations.py`: compliance benchmark, ablations
- `uv run --group finetune python finetuning/train.py`: train the clause classifier (Apple GPU / CUDA / CPU,
  or [Colab](finetuning/notebooks/train_colab.ipynb)), `finetuning/evaluate.py` to compare it with the baselines
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

See [docs/architecture.md](docs/architecture.md), [docs/decisions.md](docs/decisions.md), [docs/mcp.md](docs/mcp.md),
[docs/data_card.md](docs/data_card.md), [docs/report_notes.md](docs/report_notes.md) and the [demo script](docs/demo.md).
