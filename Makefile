.DEFAULT_GOAL := help
.PHONY: help install lint format typecheck test test-all check qdrant-up qdrant-down clean

UV ?= uv

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-14s\033[0m %s\n", $$1, $$2}'

install: ## Sync pinned environment and install pre-commit hooks
	$(UV) sync
	$(UV) run pre-commit install

lint: ## Ruff lint + format check
	$(UV) run ruff check .
	$(UV) run ruff format --check .

format: ## Auto-fix lint issues and format
	$(UV) run ruff check --fix .
	$(UV) run ruff format .

typecheck: ## mypy (strict) on src/
	$(UV) run mypy

test: ## Fast tests (no slow/integration)
	$(UV) run pytest -m "not slow and not integration"

test-all: ## All tests, including slow and integration
	$(UV) run pytest

check: lint typecheck test ## Everything CI runs

qdrant-up: ## Start optional Qdrant server (Docker)
	docker compose up -d qdrant

qdrant-down: ## Stop Qdrant server
	docker compose down

clean: ## Remove caches
	rm -rf .pytest_cache .ruff_cache .mypy_cache htmlcov .coverage
	find . -name __pycache__ -type d -prune -exec rm -rf {} +
