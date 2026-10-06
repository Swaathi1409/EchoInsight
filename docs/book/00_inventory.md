# docs/book/00_inventory.md
# EchoInsight Project Inventory
# Generated: 2026-10-06
# Every source file of interest with a one-line purpose.
# Excludes: __pycache__/, node_modules/, .git/, .pytest_cache/, dist/

## Backend Modules

| File | Purpose |
|------|---------|
| backend/__init__.py | Package marker |
| backend/api/main.py | FastAPI app factory, lifespan, middleware, router mounting |
| backend/api/conversations.py | Conversation CRUD, turn append, end, analysis, jobs (37KB) |
| backend/api/admin.py | Admin: users, agents, teams, checklists, audit log |
| backend/api/auth.py | Login endpoint, JWT issue |
| backend/api/health.py | GET /health and GET /ready |
| backend/api/metrics.py | Analytics overview, agent metrics |
| backend/api/stream.py | Server-sent events for live streaming |
| backend/api/cases.py | Case management |
| backend/api/deps.py | FastAPI dependency: current user + scoped access |
| backend/api/audit.py | Audit log write helper |
| backend/models.py | All 20 SQLAlchemy ORM models |
| backend/schemas.py | All Pydantic request/response schemas |
| backend/domain_model.py | Enums, constants, shared types (no internal imports) |
| backend/db.py | Engine init, session factory, get_db_session |
| backend/auth.py | argon2 hashing, JWT encode/decode |
| backend/bootstrap.py | Idempotent QA checklist seeding from YAML |
| backend/config/settings.py | All env vars, Pydantic-settings |
| backend/config/checklist_v1.yaml | QA checklist: 6 items, weights, criticality |
| backend/config/policy_example_v1.yaml | Policy example (secondary reference) |
| backend/config/taxonomy.yaml | Call-reason taxonomy |
| backend/llm/client.py | Async LLM client, provider priority, retry, budget |
| backend/llm/prompts.py | All prompt templates and JSON schemas |
| backend/llm/budget.py | Daily token budget enforcer |
| backend/ingest/redactor.py | 9-pattern regex PII redactor |
| backend/ingest/assignment.py | Synthetic agent/team assignment |
| backend/analysis/pipeline.py | Final analysis orchestration (388 lines) |
| backend/analysis/incremental.py | Per-turn LLM extraction and state update |
| backend/state/reducer.py | Pure state reducer: merges extraction into provisional state |
| backend/qa/scorer.py | QA scoring formula |
| backend/qa/verification.py | Selective second-LLM verification |
| backend/qa/phrase_matcher.py | Deterministic keyword/regex checks for 4 QA items |
| backend/validator/evidence_gate.py | Exact-quote substring check |
| backend/validator/hard_gate.py | 7-condition structural validation |
| backend/worker/main.py | Job polling worker |
| backend/action_layer/__init__.py | Action Layer package init |
| backend/action_layer/agent_insights.py | Per-agent action data aggregation |
| backend/action_layer/config.py | Action Layer config |
| backend/action_layer/demo_seeder.py | Demo data seeder for PostgreSQL deployments |
| backend/action_layer/derive_job.py | Derives action items from analysis results |
| backend/action_layer/draft_builder.py | Draft builder for action items |
| backend/action_layer/guard.py | Guard conditions for action layer |
| backend/action_layer/issues_derive_job.py | Derives recurring issues |
| backend/action_layer/models.py | Action Layer ORM models (act_* tables) |
| backend/action_layer/phrase_lists.py | Phrase lists for pattern matching |
| backend/action_layer/playbook.py | Associates action items with playbook steps |
| backend/action_layer/prevention_library.py | Prevention suggestion library |
| backend/action_layer/recurrence_engine.py | Recurring issue pattern detection |
| backend/action_layer/repository.py | Action Layer DB access layer |
| backend/action_layer/risk_engine.py | Multi-factor risk index computation |
| backend/action_layer/workflow.py | Action item workflow management |
| backend/assistant/__init__.py | Assistant package init |
| backend/assistant/calc_tools.py | Arithmetic tool functions for assistant |
| backend/assistant/checks.py | Assistant safety checks |
| backend/assistant/known_caveats.yaml | Known caveats for assistant responses |
| backend/assistant/llm_adapter.py | LLM adapter for assistant |
| backend/assistant/models.py | Assistant ORM models (asst_* tables) |
| backend/assistant/pipeline.py | Tool-calling LLM pipeline |
| backend/assistant/settings.py | Assistant feature settings |
| backend/assistant/tool_executor.py | Dispatches tool calls |
| backend/assistant/tool_registry.py | Tool registration |
| backend/assistant/tools.yaml | Tool definitions |
| backend/alembic/env.py | Alembic environment config |
| backend/alembic/versions/0001_initial_schema.py | Initial schema migration |
| backend/alembic/versions/0002_action_layer_tables.py | Action Layer tables |
| backend/alembic/versions/0003_assistant_tables.py | Assistant tables |
| backend/alembic/versions/0004_missing_tables_and_columns.py | Patch migration |
| backend/alembic/versions/5f59b919...add_qa_checklist_tables.py | Checklist versioning |
| backend/Dockerfile | Backend Docker image definition |

## Frontend

| File | Purpose |
|------|---------|
| frontend/src/main.jsx | React entry point |
| frontend/src/App.jsx | Router, auth state, theme toggle |
| frontend/src/api.js | All API client functions |
| frontend/src/index.css | Design system: tokens, themes, global styles |
| frontend/src/components/Login.jsx | Login form |
| frontend/src/components/Dashboard.jsx | Main dashboard: KPIs, charts, conversation table |
| frontend/src/components/ConversationDetail.jsx | Transcript, QA panel, commitments, review |
| frontend/src/components/LiveDemo.jsx | Scripted live demonstration |
| frontend/src/components/LiveAppendPanel.jsx | Real-time turn append |
| frontend/src/components/AssistantPage.jsx | Full-page chat assistant |
| frontend/src/components/AssistantPanel.jsx | Embedded assistant panel |
| frontend/src/components/AdminPanel.jsx | Admin panel: all admin features |
| frontend/Dockerfile | Frontend Docker image (Nginx) |
| frontend/nginx.conf | Nginx production config |
| frontend/vite.config.js | Vite build and proxy config |
| frontend/vercel.json | Vercel SPA routing |
| frontend/package.json | NPM dependencies |

## Tests

| File | Purpose |
|------|---------|
| tests/conftest.py | Shared fixtures: in-memory SQLite DB, test client |
| tests/unit/test_qa_scorer.py | QA scoring formula correctness |
| tests/unit/test_qa_fixtures.py | 30 synthetic QA fixture tests |
| tests/unit/test_evidence_gate.py | Evidence gate: match, mismatch, edge cases |
| tests/unit/test_hard_gate.py | Hard gate: all 7 conditions |
| tests/unit/test_phrase_matcher.py | Phrase matcher: prohibited phrases, greeting |
| tests/unit/test_reducer.py | State reducer: state merge, commitment transitions |
| tests/unit/test_redactor.py | Redactor: all 9 patterns, name context |
| tests/unit/test_leakage.py | Gold-set test ID isolation |
| tests/unit/test_health.py | Health and readiness endpoints |
| tests/integration/test_lifecycle.py | Full conversation lifecycle |
| tests/integration/test_security.py | Auth, role scoping, parameter tampering |
| tests/integration/test_edge_cases.py | Idempotency, oversized body, empty analysis |

## Scripts and Config

| File | Purpose |
|------|---------|
| scripts/seed_demo.py | Demo data seeding script |
| scripts/e2e_test.py | End-to-end test runner |
| scripts/generate_docs.py | Original doc generation script |
| scripts/capture_baseline.py | Captures API golden snapshots |
| scripts/capture_screenshots.py | Captures UI screenshots |
| scripts/backup.sh | Database backup script |
| scripts/restore.sh | Database restore script |
| Makefile | Build targets: test, eval, seed, docker |
| render.yaml | Render.com deployment config |
| docker-compose.yml | Local dev Docker stack |
| docker-compose.prod.yml | Production Docker stack |
| .env.example | Environment variable template |
| pyproject.toml | Python project config |
| seed_demo_full.py | Full demo database seeder |

## Docs

| File | Purpose |
|------|---------|
| docs/architecture-decisions.md | 10 ADRs with alternatives and rationale |
| docs/architecture.md | System architecture overview |
| docs/dataset.md | Dataset source, schema, profiling, license |
| docs/deployment.md | Deployment guide |
| docs/evaluation.md | Evaluation methodology and results |
| docs/security.md | Security measures and gaps |
| docs/bug-report.md | 23 open bugs (D1-D23) |
| docs/health-report.md | System health measurements |
| docs/checkpoints.md | Development checkpoints |
| docs/adr-001-action-layer.md | Action layer ADR |
| docs/api.md | API reference |
| docs/audit-final.md | Final audit results |
| docs/seed-coverage.md | Seed database coverage |
| evals/results/eval_20261002T105635Z.json | Eval run result (sample_size=0, all provisional) |
| evals/gold_workbook.csv | Gold annotation workbook (empty, requires human annotation) |
| evals/rubric.md | Annotation rubric |
| evals/run_eval.py | Eval pipeline runner |
| proceedings.md | Development phase log and handoff records |

## Excluded Files (Reason)

| Path | Reason |
|------|--------|
| backend/__pycache__/ | Generated Python bytecache |
| frontend/node_modules/ | Vendored NPM packages |
| frontend/dist/ | Generated Vite build output |
| .git/ | Git internal data |
| .pytest_cache/ | Pytest cache |
| demo_seed.db | Binary SQLite snapshot |
| dev_local.db | Local database instance |
| test_db.sqlite | Test database artifact |
| prompts/ | Empty directory (prompts live in backend/llm/prompts.py) |
