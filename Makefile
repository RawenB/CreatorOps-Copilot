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

qdrant:
	docker compose up -d qdrant

.PHONY: install lint format test check qdrant
