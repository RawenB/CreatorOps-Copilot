# Decision Log

Every trade-off or deviation from `PROJECT_BRIEF.md` is recorded here. Format: context, decision, consequences.
Status is one of: **accepted**, **provisional** (to be confirmed by a measurement), **superseded**.

---

## D-001: Python 3.11 managed by uv with a lockfile
- **Status:** accepted (2026-11-21)
- **Context:** The brief requires Python 3.11, pinned dependencies and reproducibility. The dev Mac ships Python 3.9.
- **Decision:** Use `uv` to install and manage Python 3.11 (`.python-version`). `pyproject.toml` declares ranges, `uv.lock` pins exact versions. CI installs with `uv sync --frozen`.
- **Consequences:** The environment is reproduced the same way on the Mac, the Windows PC and CI. Contributors need `uv` installed.

## D-002: Local LLM only (Ollama), behind an `LLMClient` interface
- **Status:** accepted (owner decision, 2026-11-21). The default model is **provisional**.
- **Context:** The brief suggests one hosted provider (Anthropic) and one local provider (Ollama). The owner chose **Ollama only**: no API key and no budget.
- **Decision:**
  - Providers: `ollama` (real) and `fake` (deterministic, offline, used by tests and CI). The `LLMClient` interface stays provider-agnostic, so a hosted provider can still be added later.
  - Default agent model: `qwen3:8b`. It supports native tool calling and runs on a laptop. Default judge model: `qwen3:14b`. Both are provisional. Phase 2 confirms or replaces them with a small benchmark on routing and tool-call accuracy, and the measured numbers will be recorded here.
- **Consequences:**
  - Agent quality and latency are bounded by local hardware. Latency is reported honestly in the eval.
  - **LLM-as-judge with a local model is less reliable.** Mitigations: a fixed rubric, the judge model is larger than the agent model, and a manual spot-check on a sample measures judge–human agreement. This is listed as a limitation in the report.
  - "Token cost" metrics are reported as token counts and wall-clock time, not dollars.
  - The CI never calls an LLM.

## D-003: Custom React web UI instead of Streamlit/Gradio
- **Status:** accepted (owner decision, 2026-11-21)
- **Context:** The brief defaults to Streamlit/Gradio. The owner prefers a custom React UI for a more polished demo.
- **Decision:** React + TypeScript (Vite) in `app/`, talking to the FastAPI backend. Panels: chat, sources (highlighted passages), SQL (query + rows), approvals queue, calendar.
- **Consequences:** This takes more time than Streamlit. Mitigations: the FastAPI contract (typed Pydantic schemas) is built and tested first in Phase 2. The UI is built in Phase 3 against that contract, limited to the five panels above, with a component library to avoid custom CSS work. Node 24 is available on the dev Mac.

## D-004: Qdrant as vector store, embedded local mode by default
- **Status:** accepted (2026-11-21)
- **Context:** The store must support upserts and metadata filters (platform, version, `is_latest`, doc_type). Docker availability on the Windows PC is unconfirmed, and the Docker daemon is not always running on the Mac.
- **Decision:** Use Qdrant through `qdrant-client`. The default `CREATOROPS_QDRANT_MODE=local` uses embedded on-disk storage and needs no server. `server` mode uses `docker compose up qdrant`.
- **Consequences:** It works with or without Docker using the same code. Local mode is single-process, which is fine for a single-user demo.

## D-005: MLflow (local file store) for experiment tracking
- **Status:** accepted (2026-11-21)
- **Decision:** MLflow with a local `mlruns/` store (git-ignored). It needs no account and works offline. Colab/Kaggle fine-tuning runs export their MLflow run directory, which is then imported locally.
- **Consequences:** Summaries of runs go in `reports/`. Raw run stores are not committed.

## D-006: Instagram is the priority platform
- **Status:** accepted (owner decision, 2026-11-21)
- **Decision:** Instagram/Meta policy pages get the most coverage and the most version snapshots, and they are used for the demo scenarios. TikTok and YouTube are covered with fewer pages.
- **Consequences:** The eval set's policy questions are weighted toward Instagram. This is stated in the eval protocol.

## D-007: English for code, docs, report and presentation
- **Status:** accepted (owner decision, 2026-11-21)

## D-008: Add dependencies in the phase that first uses them
- **Status:** accepted (2026-11-21)
- **Context:** The full stack (LangGraph, Qdrant, sentence-transformers, FastAPI, MCP…) is heavy.
- **Decision:** Phase 0 installs only config and dev tooling. Each feature branch adds the dependencies it needs, in the same commit as the code that uses them.
- **Consequences:** Installs and CI stay fast early on. The git history shows clearly why each dependency exists.

## D-009: Default embedding model `bge-base-en-v1.5`, `bge-m3` in the ablation
- **Status:** provisional (2026-11-21)
- **Context:** The corpus is English. `bge-base` is about 110M parameters and fast on CPU. `bge-m3` is about 570M parameters, multilingual and slower.
- **Decision:** Start with `bge-base-en-v1.5`. Compare it with `bge-m3` in the retrieval ablation and keep the better one, based on measured Recall@k/MRR versus indexing time.
