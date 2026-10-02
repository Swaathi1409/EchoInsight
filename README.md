# EchoInsight

Telecom contact center conversation intelligence and agent quality platform.

## What it does

- Ingest call transcripts (turn-by-turn or batch)
- Redact PII before storage (phone, email, account numbers, card numbers)
- Per-turn provisional state: resolution, sentiment, churn signals, commitments
- Final LLM analysis (Groq) on conversation end: summary, call reasons, resolution, churn risk
- QA scoring: 6-item checklist with coverage, weighted score, evidence quotes, critical violation detection
- Evidence gate: every LLM quote verified as exact substring of redacted transcript
- Role-scoped access: admin / supervisor / agent
- Dashboard: overview KPIs, conversation table, transcript drill-down, QA panel, live demo

## Quick Start (local, no Docker)

```bash
# 1. Clone and set PYTHONPATH
git clone https://github.com/Swaathi1409/EchoInsight
cd EchoInsight

# 2. Install Python deps
pip install fastapi uvicorn[standard] sqlalchemy[asyncio] aiosqlite asyncpg \
    alembic pydantic pydantic-settings structlog python-jose[cryptography] \
    passlib[argon2] groq tenacity pytest pytest-asyncio httpx

# 3. Configure environment
cp .env.example .env   # add GROQ_API_KEY and SECRET_KEY

# 4. Run backend (SQLite for local dev)
DATABASE_URL=sqlite+aiosqlite:///./dev.db uvicorn backend.api.main:app --reload

# 5. Seed admin user (optional)
DATABASE_URL=sqlite+aiosqlite:///./dev.db SEED_USERS=admin:changeme:admin \
    python -m backend.scripts.seed_users

# 6. Run frontend
cd frontend && npm install && npm run dev
```

Open http://localhost:3000 — login with `admin`/`changeme`.

## Quick Start (Docker Compose)

```bash
# Start DB and API
docker compose up db api

# Run migrations
docker compose --profile migrate up migrate

# Seed users
SEED_USERS=admin:changeme:admin docker compose --profile seed up seed

# Start worker (for background analysis jobs)
docker compose --profile worker up worker -d
```

## Running Tests

```bash
# All critical tests (unit + integration, no real API calls)
python -m pytest tests/unit/ tests/integration/ -v

# With coverage
python -m pytest tests/unit/ tests/integration/ --cov=backend --cov-report=term-missing
```

## Architecture

```
POST /api/v1/conversations/{id}/turns
  -> PII Redaction (backend/ingest/redactor.py)
  -> Store Turn (SQLite / PostgreSQL)
  -> Queue per-turn extraction job

POST /api/v1/conversations/{id}/end
  -> Mark ended
  -> Queue final_analysis job

Worker (backend/worker/main.py)
  -> Poll jobs table
  -> run_final_analysis()
      -> LLM call (Groq, JSON schema mode)
      -> Evidence gate (every quote verified)
      -> QA score (6 items, weighted, coverage)
      -> Persist Analysis + QAResult + Commitments
```

## Key Design Decisions

- **No original text stored** (`store_original_text=False`): only redacted text hits the DB and LLM
- **Evidence gate**: LLM hallucinations are blocked — quotes must be exact substrings
- **Synthetic agent assignment**: deterministic hash(conversation_id) -> agent/team, no manual assignment needed
- **`sa.JSON` for JSON columns**: works on both SQLite (unit tests) and PostgreSQL (production)
- **Idempotent turn append**: `idempotency_key` prevents duplicate turns on retry
- **QA coverage threshold**: scores below 70% coverage are labelled "partial" not final

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `GROQ_API_KEY` | Groq API key (required) | — |
| `SECRET_KEY` | 64-char hex for JWT signing (required) | — |
| `DATABASE_URL` | SQLAlchemy async URL | postgresql+asyncpg://... |
| `APP_ENV` | development / production / test | development |
| `LLM_PRIMARY_MODEL` | Groq model ID | qwen/qwen3.8-27b |
| `SEED_USERS` | user:pass:role,... | admin:changeme_admin:admin |
| `LOG_LEVEL` | INFO / WARNING / DEBUG | INFO |

## API Reference

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Liveness check |
| GET | `/ready` | Readiness: DB + migrations |
| POST | `/api/v1/auth/login` | Get JWT token |
| POST | `/api/v1/conversations` | Create conversation |
| GET | `/api/v1/conversations` | List conversations (scoped) |
| GET | `/api/v1/conversations/{id}` | Detail with turns |
| POST | `/api/v1/conversations/{id}/turns` | Append turn (idempotent) |
| POST | `/api/v1/conversations/{id}/end` | End + queue analysis |
| POST | `/api/v1/conversations/submit` | Batch ingest |
| GET | `/api/v1/conversations/{id}/analysis` | Get analysis result |
| GET | `/api/v1/conversations/{id}/jobs` | Job status |

Interactive docs: http://localhost:8000/docs
