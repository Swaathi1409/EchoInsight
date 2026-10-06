# EchoInsight

A telecom contact center conversation intelligence and agent quality platform. It ingests call transcripts, redacts PII before storage, runs LLM-powered analysis on conversation end, scores agent quality against a weighted checklist, and presents everything through a role-scoped dashboard.

Live deployment: https://echoinsight-telecom-intelligence.vercel.app

---

## Test Credentials

The deployed instance runs on a pre-seeded SQLite database with representative call data. You can log in immediately with the following accounts:

| Username | Password | Role | Access |
|---|---|---|---|
| admin | admin123 | Admin | Full access to all conversations, analytics, admin panel, and system settings |
| agent1 | agent1pass | Agent | Scoped to own conversations only (linked to agent_00, 15 analyzed calls) |
| agent2 | agent2pass | Agent | Scoped to own conversations only (linked to agent_02, 6 analyzed calls) |

---

## What You Can Test and What Each Feature Does

### Dashboard (/)
Overview of the entire contact center. Shows total conversations, analysis completion rate, average QA score, churn risk distribution, and resolution breakdown. Use this to understand the platform's health at a glance.

The admin account will show all 49 seeded conversations across all agents and teams.

### Conversation List (/conversations)
A sortable, filterable table of all conversations accessible to the logged-in user. Columns include agent name, team, QA score, resolution, churn risk, and status. Click any row to go to the detail view.

### Conversation Detail (/conversations/:id)
The core view of the platform. For any analyzed conversation you can see:

- Full redacted transcript, turn by turn, with speaker labels
- AI-generated summary, call reason(s), and detected resolution outcome
- QA scorecard: 6 checklist items (greeting, identity verification, empathy, disclosure, prohibited promises, closure), each with a pass/fail verdict, confidence score, cited evidence quote from the transcript, and evidence type
- Churn risk label with supporting signals
- Commitment ledger: every promise made by the agent during the call, with status (proposed, accepted, scheduled, completed, cancelled, uncertain) and deadline if mentioned
- Job status panel showing whether the background analysis job has completed
- False resolution flag if the LLM detected the resolution claim does not match the evidence

### Live Demo (/live-demo)
An interactive simulation of the live call monitoring flow. A scripted conversation between a customer and an agent plays out turn by turn. After each agent turn, a per-turn LLM extraction updates the provisional state panel on the right, showing how the system builds its understanding of the call incrementally before the final analysis runs on end. Good for demonstrating the real-time intelligence capability.

### Quality Overview
Aggregated QA metrics across the visible conversation set. Shows average scores by checklist item, coverage rates, and how many calls have critical violations or are pending human review. Helps identify which QA dimensions agents struggle with most.

### Open Commitments
A queue of all commitments extracted from calls that have not yet been marked completed. Use this to follow up on agent promises such as callbacks, refunds, and escalations.

### Cases
Links related conversations to a case. Useful for tracking a customer issue across multiple call attempts.

### Admin Panel (/admin)
Available only to the admin account. Contains:

- User management: create, list, and manage user accounts with role assignments
- Checklist manager: view the active QA checklist version (6 items with weights and criticality flags)
- Audit log: a record of all sensitive actions performed in the system
- System health: token budget usage, job queue depth, and API health status
- Metrics: Prometheus-format metrics for the API process

### Chat Assistant
An embedded assistant that can answer questions about conversations and the system using tool-calling. It is read-only and cannot modify any data. Useful for natural-language queries such as "which calls had a churn risk this week" or "summarize the commitments from conversation X".

---

## Architecture

EchoInsight is a modular monolith. The backend is a FastAPI application deployed on Render as a single Docker container. The frontend is a React SPA deployed on Vercel. SQLite is used for the live deployment via a pre-seeded snapshot (`demo_seed.db`) that is restored at boot.

```
Users (Browser)
    |
    | HTTPS + JWT
    |
Vercel (React SPA)
    |
    | REST API calls
    |
Render (FastAPI, Docker)
    |
    |-- Ingest & Redact (9 regex patterns, PII removed before storage)
    |        [REDACTION BOUNDARY]
    |-- Store turn in SQLite (text_redacted only, original discarded)
    |-- Queue background job
    |
    |-- Background Worker (polls every 5s)
    |      |
    |      |-- Load full transcript
    |      |-- SYSTEM_FINAL LLM call (via OpenRouter -> qwen/qwen3.8-27b)
    |      |-- Evidence Gate (LLM quotes must be exact substrings of redacted text)
    |      |-- SYSTEM_QA LLM call (6-item checklist scoring)
    |      |-- Phrase Matcher (deterministic regex override for 4 items)
    |      |-- Selective Verification (second LLM call for critical/uncertain items)
    |      |-- Hard Gate (7 structural checks)
    |      |-- QA Scorer (coverage, weights, critical violation cap at 60)
    |      |-- Persist: Analysis + QAResult + Commitments
    |
    |-- SQLite (demo_seed.db, restored at boot)
```

**Architecture documentation:** [docs/architecture.md](docs/architecture.md)

<img width="3300" height="2550" alt="echoinsight_architecture" src="https://github.com/user-attachments/assets/a71fcdf2-c5ab-4d38-a870-6a152b516733" />

---

## Key Design Decisions

**Redaction before storage.** The original turn text is never written to disk, never logged, and never sent to the LLM. Only the redacted text (with tags like `[PHONE]`, `[CARD]`, `[EMAIL]`) is stored. This is enforced in `backend/ingest/redactor.py` and is not configurable at runtime.

**Evidence gate.** Every quote the LLM returns is checked as an exact substring of the redacted transcript. If it does not match, the QA item is downgraded to `needs_review` and flagged for human review. This makes hallucinated citations structurally impossible to slip through undetected.

**OpenRouter as primary LLM provider.** The system was designed to work with any OpenAI-compatible endpoint. In the current deployment, `OPENROUTER_API_KEY` is set, which makes OpenRouter the active provider. Groq remains as a fallback. The primary model is `anthropic/claude-haiku-4.5` via OpenRouter for the live deployment.

**Deterministic phrase matching.** Four QA checklist items (greeting, empathy, closure, disclosure) are evaluated using a regex phrase matcher in addition to the LLM. If the matcher detects the phrase with high confidence, it overrides a weaker LLM verdict. This reduces unnecessary LLM calls and improves consistency on scripted phrases.

**SQLite for demo deployment.** The live deployment at Render uses the `demo_seed.db` SQLite snapshot that is committed to the repository. At boot, if the database file is missing, it is restored from this snapshot. This makes the demo fully self-contained and avoids managing a separate database service on free-tier hosting. A PostgreSQL path is also supported for production scale.

**Synthetic agent assignment.** Because the dataset has no real agent roster, agents and teams are assigned deterministically by `hash(conversation_id) % 25`. This assignment is labeled `synthetic_assignment=true` in the database and displayed as such in the UI.

**Job table as queue.** Background analysis jobs are tracked in the `jobs` database table with status, attempt count, and error fields. There is no external queue service (no Redis, no Celery). This keeps the deployment simple at the cost of not scaling horizontally without changes.

---

## Local Development Setup

```bash
git clone https://github.com/Swaathi1409/EchoInsight.git
cd EchoInsight

# Install Python dependencies
pip install -r requirements.txt

# Copy environment file and fill in values
cp .env.example .env
# At minimum, set OPENROUTER_API_KEY (or GROQ_API_KEY) and SECRET_KEY

# Run the backend (SQLite, demo seed restored automatically at first boot)
uvicorn backend.api.main:app --reload --port 8000

# In a separate terminal, run the background worker
python -m backend.worker.main

# In a separate terminal, run the frontend
cd frontend
npm install
npm run dev
```

Open http://localhost:5173 and log in with the credentials in the section above.

The demo seed is restored automatically on first boot when `dev_local.db` does not exist and `demo_seed.db` is present in the project root.

---

## Running with Docker Compose

```bash
# Start API and worker together
docker compose up

# Or start only the API (worker is embedded in the same compose file)
docker compose up api
```

---

## Running Tests

```bash
# Full test suite (259 tests, no real LLM calls, no network)
python -m pytest tests/ -v

# Unit tests only (fastest, sub-second)
python -m pytest tests/unit/ -v

# With coverage report
python -m pytest tests/ --cov=backend --cov-report=term-missing
```

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `OPENROUTER_API_KEY` | Recommended | — | OpenRouter API key. Takes priority over Groq when set. |
| `GROQ_API_KEY` | Fallback | — | Groq API key. Used if OpenRouter key is not set. |
| `SECRET_KEY` | Yes | — | 64-character hex string for JWT signing. |
| `DATABASE_URL` | No | SQLite local file | Async database URL. Uses SQLite by default for local dev. |
| `LLM_PRIMARY_MODEL` | No | `qwen/qwen3.8-27b` | Model for turn extraction and final analysis. |
| `LLM_VERIFIER_MODEL` | No | `openai/gpt-oss-20b` | Model for selective QA verification. |
| `OPENROUTER_MODEL` | No | `anthropic/claude-haiku-4.5` | Model used when routing via OpenRouter. |
| `LLM_DAILY_TOKEN_BUDGET` | No | `400000` | Daily token cap (in-process counter, resets on restart). |
| `SEED_USERS` | No | `admin:changeme_admin:admin` | Comma-separated `username:password:role` to seed on boot. |
| `SEED_DEMO_DATA` | No | `false` | Set `true` on PostgreSQL deployments to seed demo data at boot. |
| `STORE_ORIGINAL_TEXT` | No | `false` | Keep false. Storing original text requires encryption not in scope. |
| `EMBEDDINGS_ENABLED` | No | `false` | Enables embedding-based phrase matcher. Off until measurably beneficial. |
| `ACTION_LAYER_ENABLED` | No | `false` | Enables PDCA risk engine and recovery desk. Off by default. |
| `CORS_ALLOWED_ORIGINS` | No | localhost origins | Comma-separated list of allowed frontend origins. |
| `APP_ENV` | No | `development` | One of: `development`, `production`, `test`. |
| `LOG_LEVEL` | No | `INFO` | Log verbosity. |

Generate a SECRET_KEY:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

---

## API Reference

| Method | Path | Auth | Description |
|---|---|---|---|
| GET | `/health` | Public | Liveness check |
| GET | `/ready` | Public | Readiness: DB connection and migration version |
| GET | `/metrics` | Admin | Prometheus-format metrics |
| POST | `/api/v1/auth/login` | Public | Returns JWT token |
| POST | `/api/v1/conversations` | All | Create a new conversation |
| GET | `/api/v1/conversations` | Scoped | List conversations (filtered by role) |
| GET | `/api/v1/conversations/{id}` | Scoped | Conversation detail with turns |
| POST | `/api/v1/conversations/{id}/turns` | Scoped | Append a turn (idempotent via key) |
| POST | `/api/v1/conversations/{id}/end` | Scoped | End conversation and queue analysis |
| POST | `/api/v1/conversations/submit` | All | Batch transcript ingest |
| GET | `/api/v1/conversations/{id}/analysis` | Scoped | Get full analysis result |
| GET | `/api/v1/conversations/{id}/jobs` | Scoped | Check job status |
| GET | `/api/v1/conversations/open-commitments` | Scoped | Open commitment queue |
| GET | `/api/v1/analytics/agent/{agent_id}` | Scoped | Agent-level analytics |
| GET | `/api/v1/analytics/team/{team_id}` | Scoped | Team-level analytics |
| GET/POST | `/api/v1/admin/*` | Admin | User and system management |
| GET/POST | `/api/v1/cases/*` | Scoped | Case management |
| GET/POST | `/api/v1/assistant/*` | All | Chat assistant (read-only) |

Interactive API docs (local): http://localhost:8000/docs

---

## Project Structure

```
EchoInsight/
  backend/
    api/            - FastAPI routers (conversations, auth, admin, health, metrics, cases)
    ingest/         - PII redactor and synthetic agent assignment
    llm/            - LLM client, prompt templates, token budget
    analysis/       - Final analysis pipeline and incremental per-turn extraction
    state/          - Pure-function state reducer for provisional state merging
    qa/             - QA scorer, phrase matcher, selective verification
    validator/      - Evidence gate and hard gate
    worker/         - Background job poller (idle sweep, final analysis runner)
    config/         - Settings (Pydantic-settings), checklist YAML, taxonomy YAML
    models.py       - SQLAlchemy ORM models (20 tables)
    domain_model.py - Enums and constants
    bootstrap.py    - Startup seeding for checklists and users
  frontend/
    src/
      components/   - React components for all pages
      api.js        - All fetch wrappers with JWT attachment
  docs/
    architecture/   - Architecture documentation and reports
    submission/     - Rubric mapping, health evals, additional exploration
    architecture-decisions.md  - 10 ADRs with context and trade-offs
    bug-report.md   - Open known issues
    deployment.md   - Deployment guide
  tests/
    unit/           - Fast tests, no DB, no LLM (sub-second)
    integration/    - SQLite in-memory, no LLM
  evals/            - Evaluation pipeline and gold workbook
  demo_seed.db      - Pre-seeded SQLite snapshot (restored at boot)
  seed_demo_full.py - Script used to generate the demo seed
  render.yaml       - Render.com deployment config
```

---

## Deployment Notes

The live deployment at https://echoinsight-telecom-intelligence.vercel.app uses:

- Frontend: Vercel (static React SPA build)
- Backend: Render.com free-tier Docker web service
- Database: SQLite, restored from `demo_seed.db` at each boot

The Render free tier suspends the backend after 15 minutes of inactivity. The first request after a period of inactivity may take 30 to 60 seconds to respond while the container wakes up. This is expected behavior on the free tier.

For a production deployment with persistent data, set `DATABASE_URL` to a PostgreSQL connection string and set `SEED_DEMO_DATA=true` to populate the demo data on first boot.

---

## Documentation

| Document | Purpose |
|---|---|
| [docs/architecture.md](docs/architecture.md) | Full system narrative |
| [docs/architecture-decisions.md](docs/architecture-decisions.md) | 10 architecture decision records |
| [docs/deployment.md](docs/deployment.md) | Deployment guide for Docker and cloud platforms |
| [docs/bug-report.md](docs/bug-report.md) | Open known issues |
| [docs/submission/RUBRIC_MAPPING.md](docs/submission/RUBRIC_MAPPING.md) | Rubric self-assessment |
| [docs/submission/ADDITIONAL_EXPLORATION.md](docs/submission/ADDITIONAL_EXPLORATION.md) | Explorations beyond the assignment |
| [docs/submission/SYSTEM_HEALTH_EVALS.md](docs/submission/SYSTEM_HEALTH_EVALS.md) | System health and eval metrics |

---

## Screenshots

Dashboard - Overview:

<img width="1365" height="675" alt="image" src="https://github.com/user-attachments/assets/054d2512-6486-4cf0-807d-28bc7b6b6626" />


List of conversations:

<img width="1123" height="631" alt="image" src="https://github.com/user-attachments/assets/e65a8920-f835-4f92-af89-ddbb649ceb52" />


Transcript of a conversation:

<img width="1131" height="628" alt="image" src="https://github.com/user-attachments/assets/e6065bcc-f936-4b7a-8e6d-6165c5a09eca" />


Analysis of the conversation:

<img width="893" height="632" alt="image" src="https://github.com/user-attachments/assets/916c1a4b-9f2a-4833-a713-45c7e6d0f85b" />


QA Score of the conversation with evidence:

<img width="1126" height="608" alt="image" src="https://github.com/user-attachments/assets/65500f35-e128-4664-9090-12743eded823" />


Commitments proposed in the conversation:

<img width="1126" height="438" alt="image" src="https://github.com/user-attachments/assets/feac01c9-28c7-4091-bf52-c150e6fa8fbc" />


Option for an reviewer to review the work done by EchoInsight AI on a periodic basis and add comments:

<img width="1121" height="571" alt="image" src="https://github.com/user-attachments/assets/4c15eeae-7d20-4247-b223-43d7069cfdbf" />


Open commitments and its deadline:

<img width="1124" height="631" alt="image" src="https://github.com/user-attachments/assets/59c4fd6c-3c09-4ee2-9a81-a7934c33a71e" />

False resolution:

<img width="1127" height="520" alt="image" src="https://github.com/user-attachments/assets/d778d4ab-cfb8-4751-bb75-440fe096dae4" />


Live demo to test the project and see live analysis:

<img width="1365" height="680" alt="ss (2)" src="https://github.com/user-attachments/assets/55789f34-9dd5-46fa-8a70-f9f81fd01550" />


Action Intelligence Layer:

<img width="1365" height="687" alt="ss (6)" src="https://github.com/user-attachments/assets/093976fd-6ea1-4fec-8785-f63ffc59b94a" />

Recover Desk:

<img width="1123" height="612" alt="ss (10)" src="https://github.com/user-attachments/assets/36445d2a-adb4-45d2-9815-fb44d2dfd9b5" />
<img width="1126" height="610" alt="ss (11)" src="https://github.com/user-attachments/assets/f3491d2c-f3aa-478d-898c-ce2292903a48" />

Follow up Draft suggestion:

<img width="1126" height="617" alt="ss (12)" src="https://github.com/user-attachments/assets/91ace1e2-8d61-4063-bf2e-38bad562f35b" />

What if scenarios to check how risk of churning reduces or increases based on set of factors:

<img width="1365" height="668" alt="ss (14)" src="https://github.com/user-attachments/assets/60c29c4e-8f4f-48f0-b304-0d40991d13a3" />


Highlighting Recurring issue:

<img width="1365" height="667" alt="ss (15)" src="https://github.com/user-attachments/assets/38194fa2-cec2-4a3c-a3b4-b07c58e85707" />

<img width="1123" height="635" alt="ss (16)" src="https://github.com/user-attachments/assets/5a026196-7429-46ae-bdd0-8a40450558da" />


Key action layer - PDCA Initiative:

<img width="870" height="563" alt="ss (18)" src="https://github.com/user-attachments/assets/393951de-118a-4da2-b264-829bf31a1fab" />


Analyzing how different agents performs:

<img width="1365" height="688" alt="ss (19)" src="https://github.com/user-attachments/assets/37d60b20-2541-43e7-b8ce-e5bd56951313" />

<img width="1127" height="618" alt="ss (20)" src="https://github.com/user-attachments/assets/cbf8bfcb-9af8-48af-8e51-cc767c036d40" />

<img width="1147" height="630" alt="ss (21)" src="https://github.com/user-attachments/assets/f878fd11-c61e-4ba9-b18a-5c39a6a1d1ab" />


Chat Assistant:

<img width="1365" height="675" alt="ss (23)" src="https://github.com/user-attachments/assets/7afbb49e-eddf-4630-a00c-951416caa7e7" />


Help Tab in chat assistant:

<img width="1126" height="632" alt="ss (24)" src="https://github.com/user-attachments/assets/59d4f8d9-8e0c-4244-9f60-0fc8d45ea829" />

Sample conversation:

<img width="1365" height="674" alt="ss (26)" src="https://github.com/user-attachments/assets/b0a3a9fe-2edc-4ee7-888c-119acb184ea0" />
<img width="1365" height="671" alt="ss (27)" src="https://github.com/user-attachments/assets/5f5920dd-bd6c-4464-8d4a-d52091d16270" />


Admin Panel:

<img width="1365" height="688" alt="ss (28)" src="https://github.com/user-attachments/assets/700105a7-d984-427a-a15d-d8263aff685b" />

Audit logs for security and reliability purpose:

<img width="1365" height="672" alt="ss (29)" src="https://github.com/user-attachments/assets/eb3c3c39-e85e-4eb6-ac84-0daeb866c197" />

Checklists: (Example of sample policy that project follows):

<img width="1365" height="664" alt="ss (30)" src="https://github.com/user-attachments/assets/e1c199c8-c38a-40ca-a74e-a4105430ebc5" />

<img width="1232" height="672" alt="ss (1)" src="https://github.com/user-attachments/assets/8f1bcda8-df57-4735-b7cc-ef8bcb3525c5" />







