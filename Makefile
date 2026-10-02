# EchoInsight — Makefile
# Usage: make <target>
.PHONY: help dev dev-backend dev-worker dev-frontend \
        install install-dev seed test e2e lint \
        build up down logs clean deploy

PYTHON=python
PIP=pip

help:
	@echo "EchoInsight targets:"
	@echo "  make install        Install all dependencies"
	@echo "  make seed           Seed database with users + demo conversations"
	@echo "  make dev            Start all 3 services (backend + worker + frontend)"
	@echo "  make test           Run unit + integration tests"
	@echo "  make e2e            Run E2E API test suite"
	@echo "  make lint           Run ruff + mypy"
	@echo "  make build          Build Docker images"
	@echo "  make up             Start full stack via docker compose"
	@echo "  make down           Stop docker compose stack"
	@echo "  make clean          Remove __pycache__, .pyc, dist"

install:
	$(PIP) install -e "backend[dev]"
	cd frontend && npm install

seed:
	$(PYTHON) -m backend.scripts.seed_users
	$(PYTHON) scripts/seed_demo.py

dev-backend:
	uvicorn backend.api.main:app --reload --host 0.0.0.0 --port 8000

dev-worker:
	$(PYTHON) -m backend.worker.main

dev-frontend:
	cd frontend && npm run dev

# Parallel dev (Windows PowerShell — run in separate terminals)
dev:
	@echo "Start these in separate terminals:"
	@echo "  make dev-backend"
	@echo "  make dev-worker"
	@echo "  make dev-frontend"

test:
	$(PYTHON) -m pytest tests/ -v --tb=short -x

e2e:
	@echo "NOTE: Stop uvicorn --reload first, then run:"
	@echo "  uvicorn backend.api.main:app"
	$(PYTHON) scripts/e2e_test.py

lint:
	ruff check backend/ --fix
	mypy backend/ --ignore-missing-imports --no-strict-optional

build:
	docker compose build

up:
	docker compose up -d
	@echo "Waiting for db..."
	sleep 5
	docker compose exec api python -m backend.scripts.seed_users

down:
	docker compose down

logs:
	docker compose logs -f

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete 2>/dev/null || true
	rm -rf frontend/dist frontend/.vite
