install:
	uv sync

lint:
	uv run ruff check .
	uv run ruff format --check .

format:
	uv run ruff check --fix .
	uv run ruff format .

test:
	uv run pytest

check: lint test

db:
	uv run python scripts/generate_analytics_db.py

corpus: db
	uv run python scripts/download_corpus.py

ingest:
	uv run python scripts/ingest.py

api:
	uv run uvicorn creatorops.api.main:app --reload --port 8000

ui:
	cd app && npm install && npm run dev

eval:
	HF_HUB_OFFLINE=1 uv run python eval/validate_dataset.py
	HF_HUB_OFFLINE=1 uv run python eval/run_retrieval_eval.py
	HF_HUB_OFFLINE=1 uv run python eval/run_retrieval_eval.py --raw
	HF_HUB_OFFLINE=1 uv run python eval/run_agent_eval.py
	HF_HUB_OFFLINE=1 uv run python eval/run_generation_eval.py --run agent
	HF_HUB_OFFLINE=1 uv run python eval/run_sql_safety.py
	uv run python eval/make_report.py

eval-retrieval:
	HF_HUB_OFFLINE=1 uv run python eval/run_retrieval_eval.py
	uv run python eval/make_report.py

mcp:
	HF_HUB_OFFLINE=1 uv run python -m creatorops.mcp_server.server

qdrant:
	docker compose up -d qdrant

.PHONY: install lint format test check db corpus ingest api ui eval eval-retrieval mcp qdrant
