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

qdrant:
	docker compose up -d qdrant

.PHONY: install lint format test check db corpus ingest qdrant
