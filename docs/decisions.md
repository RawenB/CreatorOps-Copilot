# Decisions

Choices I made during the project and why. Changes compared to the original brief are marked.

## 1. Python 3.11 with uv
uv installs Python 3.11 and pins all versions in `uv.lock`, so the project installs the same way on my Mac,
my Windows PC and in GitHub Actions. Tooling is kept small: ruff for style and pytest for tests.

## 2. Local LLM only (Ollama) (changed from the brief)
The brief suggested a hosted API plus a local model. I don't have an API budget, so everything runs with
Ollama. The default model is `qwen3:8b` because it supports tool calling and runs on a laptop.
All LLM calls go through one small client class, so another provider could be added later.
There is also a `fake` provider that returns fixed answers, used in tests and CI.

Downsides: answers are slower and weaker than with a big hosted model, and using a local model as the judge
for generation metrics is less reliable. I will check a sample of the judge's scores by hand and mention it in
the limitations.

## 3. React UI (changed from the brief)
The brief suggested Streamlit or Gradio. I chose React (Vite + TypeScript) because it gives a better demo.
To save time, the FastAPI backend is done first and the UI only calls it.

## 4. Qdrant as vector store
Qdrant supports metadata filters (platform, version, is_latest...) and upserts, which I need for versioned
documents. It can run in local mode (just a folder, no server), which is the default. Docker is available,
so `make qdrant` can also start a real server.

## 5. MLflow for experiments
MLflow with a local folder (`mlruns/`, not committed). No account needed.

## 6. Instagram first
Instagram gets the most policy pages and snapshots and is used in the demo. TikTok and YouTube have fewer pages.

## 7. English
Code, docs, report and presentation are in English.

## 8. One-week deadline (changed from the brief)
The brief planned 4 weeks; I have 1 week. What I keep: everything required by the course (RAG with metadata
and versions, citations, MCP with tools, LangGraph, 120+ eval questions with Recall@k/MRR, one fine-tuning
experiment, web UI). What I reduce:
- corpus around 120 documents (lower end of the 120-250 target)
- fine-tuning: one small encoder model only
- ablations kept cheap (they reuse the same index and eval set)
- stretch goals (multilingual, weekly report, feedback button) are dropped

## 9. Embedding model
Start with `bge-base-en-v1.5` (small, fast on CPU). Compare with `bge-m3` in one ablation if time allows.

## 10. Dependencies
Libraries are added when the code that uses them is added, not all at the start.
