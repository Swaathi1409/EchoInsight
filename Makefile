.PHONY: help install install-dev lint typecheck test test-unit test-integration test-fast \
        migrate migrate-create run run-worker build up down clean eval \
        seed-users secret-scan fetch-pool

help:
	@echo "EchoInsight - available targets:"
	@echo "  install        Install production dependencies"
	@echo "  install-dev    Install all development dependencies"
	@echo "  lint           Run ruff linter"
	@echo "  typecheck      Run mypy type checker"
	@echo "  test           Run all tests"
	@echo "  test-unit      Run unit tests only (no database, mock LLM)"
	@echo "  test-fast      Run fast tests (unit + selected integration)"
	@echo "  migrate        Apply all pending Alembic migrations"
	@echo "  migrate-create Create a new migration (MSG=description)"
	@echo "  run            Start development API server"
	@echo "  run-worker     Start development worker process"
	@echo "  build          Build Docker images"
	@echo "  up             Start development Docker Compose stack"
	@echo "  down           Stop Docker Compose stack"
	@echo "  eval           Run evaluation suite (requires GROQ_API_KEY)"
	@echo "  seed-users     Seed initial users from SEED_USERS env var"
	@echo "  fetch-pool     Fetch analysis pool conversations from HuggingFace API"
	@echo "  secret-scan    Run gitleaks secret scanner"
	@echo "  clean          Remove build artifacts and caches"

install:
	pip install -r backend/requirements.txt

install-dev:
	pip install -r backend/requirements.txt -r backend/requirements-dev.txt

lint:
	cd backend && ruff check .
	cd backend && ruff format --check .

typecheck:
	cd backend && mypy . --ignore-missing-imports

test:
	cd backend && pytest tests/ -v --tb=short

test-unit:
	cd backend && pytest tests/unit/ -v --tb=short -m "not integration"

test-integration:
	cd backend && pytest tests/integration/ -v --tb=short

test-fast:
	cd backend && pytest tests/unit/ tests/integration/test_ingest.py tests/integration/test_lifecycle.py -v --tb=short

migrate:
	cd backend && alembic upgrade head

migrate-create:
	cd backend && alembic revision --autogenerate -m "$(MSG)"

run:
	cd backend && uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

run-worker:
	cd backend && python -m worker.main

build:
	docker compose build

up:
	docker compose up -d

down:
	docker compose down

eval:
	cd backend && python -m evals.run

seed-users:
	cd backend && python -m scripts.seed_users

fetch-pool:
	cd backend && python -m data.scripts.fetch_conversations

secret-scan:
	gitleaks detect --source . --verbose

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	rm -rf backend/.mypy_cache backend/.ruff_cache backend/.pytest_cache
	rm -rf frontend/dist frontend/node_modules 2>/dev/null || true
