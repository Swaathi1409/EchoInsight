# EchoInsight Final Audit and Baseline Report

## Baseline Summary
- **Branch created**: `final-stabilize`
- **Tag created**: `pre-final`
- **Database Backup**: Stored using `VACUUM INTO` in `.backup/dev_local_baseline.db`
- **Tests**: Ran full pytest suite. 6 failures found in `tests/unit/test_qa_fixtures.py` and `tests/unit/test_qa_scorer.py` due to recent rules changes that need to be addressed.
- **Golden Snapshots**: Captured via `scripts/capture_baseline.py` to `.backup/golden_snapshots.json`.
- **Screenshots**: Captured in 1440px and 820px across light/dark themes in `.backup/screenshots/`.

## Architecture & Infrastructure Facts
- **Database**: SQLite (using `sqlite+aiosqlite` driver) mapped via SQLAlchemy. Migrations with Alembic. Journal mode is implicitly default/WAL based on runtime configuration.
- **LLM**: Using Groq natively via `groq` SDK in `backend/llm/client.py`. OpenRouter configuration exists in `.env` but Groq is primarily utilized as default when active. Structured output uses JSON mode. Token budget guards exist.
- **Frontend**: Vite-based React single page application. Environment variables like `VITE_API_URL` dictate connection. Authentication relies on JWT passed in `Authorization: Bearer <token>` header. 
- **CORS**: Configurable via `CORS_ALLOWED_ORIGINS` setting. 
- **SSE**: Server-Sent Events are utilized for streaming insights/chats.
- **Background Jobs**: Currently run in a separate worker process (`dev-worker: python -m backend.worker.main`), but will need to be unified in-process for Render's ephemeral free tier.
- **Config & Policy**: Settings are loaded from `.env` via `pydantic_settings`.

## Table Inventory
**Domain Data (Keep in seed)**:
- teams: 5
- agents: 25
- conversations: 50
- turns: 270
- commitments: 68
- analyses: 57
- qa_results: 57
- cases: 9
- case_conversations: 9
- segments: 14
- act_items: 152
- act_item_events: 155
- act_recommendations: 402
- act_recurring_issues: 8
- act_prevention_suggestions: 12
- act_initiatives: 9
- act_initiative_events: 10
- qa_checklist: 1
- qa_checklist_version: 1
- qa_checklist_item: 6
- act_settings: 1
- asst_settings: 1

**Identity & Secrets (Exclude/Reset in seed)**:
- users: 5
- review_annotations: 1

**Transient Data (Reset in seed)**:
- jobs: 93
- audit_log: 280
- asst_session: 81
- asst_message: 252
- asst_feedback: 15
- state_events: 0
- _test_lock: 0

## Assumptions Discovered (To be addressed for Single-Instance Render Deploy)
1. **Multi-process assumption**: Currently `Makefile` specifies `dev-worker` and `dev-backend`. Render needs everything in a single `uvicorn` instance for the free tier to stay awake efficiently and avoid ephemeral state skew.
2. **PostgreSQL vs SQLite**: The system uses `BEGIN IMMEDIATE` for locks which is good for SQLite, but the multi-process design suggests a PostgreSQL concurrency model. SQLite on Render ephemeral disk will reset. Seed restore must occur at boot.

## Memory & Footprint
- SQLite `dev_local.db` size is ~2.5 MB.
- Container footprint will be small, memory is comfortably well under Render's 512MB free tier limit.
