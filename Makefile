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

mcp:
	HF_HUB_OFFLINE=1 uv run python -m creatorops.mcp_server.server

qdrant:
	docker compose up -d qdrant

.PHONY: install lint format test check db corpus ingest api ui mcp qdrant
