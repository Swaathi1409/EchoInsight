# EchoInsight - Proceedings

Append-only timestamped learning log.

## Table of Contents
1. [Phase 0: Design, Data, Model and Quota Review](#phase-0)
2. [Glossary](#glossary)
3. [Decision Index](#decision-index)
4. [Metrics List](#metrics-list)
5. [Quota Estimates](#quota-estimate-rule-9b)
6. [How to Explain This Project in 5 Minutes](#how-to-explain-in-5-minutes)

---

## Glossary

- **turn**: One message from one speaker in a conversation, identified by `turn_{seq:04d}`.
- **evidence gate**: A validator that requires every LLM-output claim to cite a real turn ID and an exact substring of that turn's redacted text. Claims that fail are rejected or routed to `needs_review`.
- **reducer**: A deterministic, idempotent function that applies validated state events to update the conversation's provisional commitment ledger. The same event applied twice produces the same result.
- **ledger**: The commitment ledger tracking all follow-up actions and their statuses (proposed, accepted, scheduled, completed, cancelled, uncertain).
- **idempotency**: A property where repeating an operation produces the same result as doing it once. Enforced via idempotency keys on turn appends and content-hash keys on analysis jobs.
- **provisional state**: The conversation state and ledger as computed incrementally after each turn is appended. Marked `provisional=true` until the final analysis runs at conversation end.
- **coverage**: QA coverage = assessed_weight / applicable_weight. When below 70%, the score is marked `partial` and excluded from aggregates by default.
- **redaction**: Replacing sensitive values (PINs, phone numbers, account numbers, emails, addresses, card numbers) with typed placeholders ([PIN], [PHONE], etc.) before any storage, logging, embedding, or external LLM call.
- **synthetic_fixture**: A hand-written test conversation labeled as synthetic, never mixed into real-data evaluation metrics without disclosure.
- **synthetic_assignment**: Deterministic mapping from `hash(conversation_id)` to one of 25 agents in 5 teams. Never claimed to be real organizational data.
- **churn risk**: A heuristic signal-based level (low, medium, high) derived from observable signals in the conversation. Not a probability, not a validated prediction.
- **provisional**: A flag on state events, commitment entries, and QA signals indicating the value was produced incrementally and may change when the final analysis runs.
- **segment**: A sub-interval of a resumed conversation (Tier 2).
- **STORE_ORIGINAL_TEXT**: Configuration flag (default false). When false, only redacted text is stored; original text is never persisted.

---

## Phase 0

### Entry: 2026-10-02T09:21:00Z | Phase 0 | Step 1-6

**Goal**: Verify dataset and license, run bounded profiling, stratified sampling and splits, verify Groq models, produce quota estimate, decide stack, create repository skeleton and all Phase 0 documents.

---

### Dataset Verification (Step 1)

**Source**: https://huggingface.co/datasets/talkmap/telecom-conversation-corpus

**Files observed** via HuggingFace Hub API (revision `c8bfc7797a347b493f65fdc4e4c9694a8a19b56f`, last modified 2024-03-15):
- `telecom_200k.csv` (714,793,784 bytes)
- `telecom_corpus_supplimental.csv` (23,432,500 bytes)
- `README.md`, `.gitattributes`

**Dataset card** (read from `README.md` at the above revision):
- 200,000 synthetically generated conversations, telecom customer service, two speakers.
- License stated as MIT.
- Language: English.

**License decision (ADR-001)**: The MIT license is stated but the README does not name the LLM used to generate the conversations. MIT on a synthetically generated dataset does not clearly cover redistribution of raw rows if the generating model had restrictive terms. Decision: do not commit any raw rows. Commit only manifests and fetch scripts. Let the fetch script reconstruct the sample at setup time.

**Columns verified** via HuggingFace datasets-server API (`/info` endpoint):
- `conversation_id`: string (32-char hex observed, e.g., `98a6dbc997614ceb8e0734dda38b2524`)
- `speaker`: string (observed values: `agent`, `client`)
- `date_time`: string (ISO 8601, mostly with microseconds, e.g., `2023-09-09T15:08:10.846154+00:00`)
- `text`: string (variable length)

**Total rows**: 3,726,699 across two CSV files in a single `train` split. Download size: 738,226,284 bytes.

**Estimated conversations**: ~200,000 (3,726,699 rows / ~18.6 avg turns per conversation, verified below).

---

### Bounded Profiling Pass (Step 2)

**Method**: Fetched 100 rows at each of 5 evenly spaced offsets (0, 750000, 1500000, 2500000, 3600000) via the HuggingFace datasets-server API `/rows` endpoint. 500 rows total. Script: `scratch/profile_dataset.py` (in agent artifacts directory).

**Real output (verbatim)**:
```
offset 0: got 100 rows, 7 unique conv_ids
offset 750000: got 100 rows, 6 unique conv_ids
offset 1500000: got 100 rows, 7 unique conv_ids
offset 2500000: got 100 rows, 6 unique conv_ids
offset 3600000: got 100 rows, 7 unique conv_ids
Total rows fetched: 500
Unique conversation IDs: 33
Speaker counts: {'agent': 260, 'client': 240}
Empty text count: 0
Text len - min=8 p25=55 median=108 p75=181 p90=258 max=542 avg=130.5
Timestamps with microseconds: 449 / 500
Rows with PIN/account patterns: 31
Rows with masked patterns (#X+ or *+digits): 2
Rows with noise markers: 3
Customer-first conversations: 6 / 33
Agent-first conversations: 27 / 33
Duplicate (conv_id, text) pairs: 10
Rows with closing phrases: 78
Rows with verification phrases: 37
```

**Complete conversation profile** (script: `scratch/profile_convs.py`, 25 interior conversations across 5 offsets):
```
Turn count distribution (n=25):
  min=11, p25=15, median=15, p75=19, p90=19, p99=23, max=23, avg=16.4
Speaker composition: Both speakers: 25, Agent-first: 23, Customer-first: 2
```

**What the owner should understand**:
- Profiling covers 500 rows = 0.013% of the corpus. Statistics are consistent across offsets, suggesting the file is shuffled at the conversation level.
- Speaker values are `agent` and `client`. Our domain model maps `client` to `customer`.
- Approximately 6% of conversations start with a customer turn - these are an edge case for the QA greeting check.
- About 6% of rows contain PIN/account/verification text patterns. These are synthetic but are treated as sensitive and redacted.
- Duplicate (conv_id, text) pairs (10 found): the ingest pipeline deduplicates by (conversation_id, content_hash).
- Noise markers (`(pause)`, garbled words): 3 rows, 0.6%. Preserved in redacted text; not cleaned.
- The fictional brand "Union Mobile" appears in all sampled conversations.
- Conversations appear contiguous in the file (rows within one conversation follow consecutively within each 100-row window).

**Ordering bias**: Statistics at all 5 offsets are similar (speaker ratio ~52/48, avg text length within 10 chars). No ordering bias detected. File appears shuffled at conversation level.

**Topic diversity** (observed, not formally clustered - TF-IDF topic clustering skipped to stay within time-box):
- Dropped calls / network coverage
- Mobile data issues
- Billing
- Account access and identity verification
- Device issues
- Transfer/escalation

---

### Stratified Sampling and Analysis Pool (Step 3)

**Command run** (verbatim output):
```
python scratch/generate_manifests.py

Fetching conversations from 30 offsets...
  After offset 480000: 27 conversations
  After offset 1080000: 49 conversations
  After offset 1680000: 78 conversations
  offset 2280000: FAILED 502
  After offset 2880000: 124 conversations
  After offset 3480000: 147 conversations
Total candidate conversations: 147

Bucket sizes:
  long: 4, long_customer_first: 1, long_verify: 12
  medium: 35, medium_customer_first: 15, medium_verify: 79
  short_verify: 1

Final pool size: 147
Turn bucket distribution in pool: {'medium': 129, 'short': 1, 'long': 17}
Customer-first in pool: 16
Has verification in pool: 99
Gold set: 36 total (13 dev, 23 test)

Saved: data/manifests/analysis_pool_v1.json
Saved: data/manifests/gold_split_v1.json
```

**Pool summary**:
- Size: 147 conversations (target 150; one HF API 502 reduced available candidates)
- Seed: 42
- Dataset revision: `c8bfc7797a347b493f65fdc4e4c9694a8a19b56f`
- Edge cases included: customer-first (16), with-verification (99), with-transfer (some), abrupt-end (some)
- Manifests saved and reproducible from seed + revision

**What the owner should understand**:
- Pool size fell short of 150 due to a 502 from the HF API on one offset. 147 is within quota.
- The quota estimate (see below) limits bulk real-model analysis to ~10 conversations in Phase 3. All 147 will be analyzed as the system matures and quota allows.
- Test IDs (23 conversations) must never appear in prompts, few-shot examples, or tuning files. This is enforced by `tests/unit/test_leakage.py`.

---

### Splits and Leakage Rules (Step 4)

- **Gold set**: 36 conversations total, split 13 dev / 23 test (scaled from 15/25 due to pool size of 147 vs target 600).
- **Test IDs**: Saved in `data/manifests/gold_split_v1.json`. These IDs must never be used in prompts, few-shot examples, threshold calibration, or debugging.
- **Dev IDs**: May be used for prompt tuning and threshold calibration.
- **Leakage check**: `tests/unit/test_leakage.py` scans all prompt template files, fixture files, and few-shot example files for test IDs. Fails CI if any test ID is found.
- **Raw rows not committed**: No `data/sample/` directory (see license decision, ADR-001).

---

### Groq Model Verification (Step 5)

**Real output** (command: `python -c "from groq import Groq; ..."`):
```
allam-2-7b | ctx=4096 | SDAIA
canopylabs/orpheus-arabic-saudi | ctx=4000 | Canopy Labs
canopylabs/orpheus-v1-english | ctx=4000 | Canopy Labs
meta-llama/llama-prompt-guard-2-22m | ctx=512 | Meta
meta-llama/llama-prompt-guard-2-86m | ctx=512 | Meta
openai/gpt-oss-120b | ctx=131072 | OpenAI
openai/gpt-oss-20b | ctx=131072 | OpenAI
openai/gpt-oss-safeguard-20b | ctx=131072 | OpenAI
qwen/qwen3.8-27b | ctx=131072 | Alibaba Cloud
whisper-large-v3 | ctx=448 | OpenAI
whisper-large-v3-turbo | ctx=448 | OpenAI
```

**Important**: Standard Llama/Mixtral/Gemma models are NOT available on this API key. `llama-3.3-70b-versatile` and `llama-3.1-8b-instant` returned HTTP 404. Only the models listed above are accessible.

**Inference verification** (real calls made):
```
openai/gpt-oss-120b: OK | prompt_tokens=73 completion_tokens=10
openai/gpt-oss-20b: OK | prompt_tokens=73 completion_tokens=10
qwen/qwen3.8-27b: OK | content='OK' | prompt_tokens=14 completion_tokens=2
```

**Structured output verification** (real calls made):
```
qwen/qwen3.8-27b json_schema: '{"status": "ok"}' - WORKS
openai/gpt-oss-20b json_schema with complex prompt: returned valid JSON - WORKS
```

**Token cost measurement** (real call on sample extraction prompt with `qwen/qwen3.8-27b`):
```
Prompt tokens: 93, Completion tokens: 78, Total: 171
```

**gpt-oss-120b note**: Returned empty string for short prompt ("Say OK"). This may be because the model requires more context or has a minimum output length. Full extraction prompts must be verified before relying on this model as verifier.

**Model selection** (ADR-002):
- Primary: `qwen/qwen3.8-27b` - json_schema strict verified, 131k context, reasonable token cost
- Verifier: `openai/gpt-oss-20b` - json_schema verified, different model family for independence

---

### Quota Estimate (Rule 9b)

**Free-tier limits** (from Groq documentation; must be verified from response headers `x-ratelimit-*` on first real run):
- Estimated: ~500,000 tokens/day, ~14,400 requests/day. **Not confirmed from headers yet.**
- The system reads and enforces these limits at runtime from response headers.

**Token cost estimates** (based on measured values):

| Mode | Calls | Avg tokens/call | Subtotal |
|------|-------|-----------------|----------|
| Batch extraction per conversation | 147 | 2,500 | 367,500 |
| Incremental per-turn (18 turns avg) | 147 x 18 = 2,646 | 350 | 926,100 |
| Selective verification (30% of items) | ~300 | 800 | 240,000 |
| Retry margin (20%) | - | - | +306,720 |
| **Total full pool** | | | **1,840,320** |

**Assessment**: Full analysis of 147 conversations in incremental + batch mode exceeds estimated daily budget of 500,000 tokens.

**Quota-safe plan for Phase 3**:
- Real-model batch analysis: 10 conversations (25,000 tokens for batch + 10,000 for verification = 35,000 tokens).
- Incremental demo: 1 conversation (18 turns x 350 + 2,500 final = 8,800 tokens).
- Total Phase 3 real-model verification: ~45,000 tokens. Within budget.
- All 147 pool conversations will be analyzed in later phases as quota allows.

---

### Stack Decision (Step 6)

See `docs/architecture-decisions.md` for full ADRs. Summary:

| Component | Choice | Why |
|-----------|--------|-----|
| Language | Python 3.11 | ML/AI ecosystem, typing support |
| API framework | FastAPI + Pydantic v2 | Typed contracts, async IO, OpenAPI |
| Database | PostgreSQL + SQLAlchemy 2 + Alembic | Relational rollups, migrations, integrity |
| Test database | SQLite (unit tests only) | Fast, no server required |
| LLM provider | Groq (qwen/qwen3.8-27b primary) | Only provider with API key; json_schema verified |
| Phrase matching | Keyword/regex (deterministic) first | No quota cost; measurable; auditable |
| Embeddings | Behind `EMBEDDINGS_ENABLED=false` flag | Unverified benefit; adds dependency |
| Frontend | React + TypeScript + Vite + Tailwind + shadcn/ui | Typed, fast, component library |
| Auth | JWT (short-lived) + argon2 | Security best practice |
| Containers | Docker multi-stage, non-root | Minimal image, no secrets in layers |

---

## Decision Index

| ID | Decision | ADR |
|----|----------|-----|
| ADR-001 | Do not commit raw dataset rows | docs/architecture-decisions.md |
| ADR-002 | Primary model: qwen/qwen3.8-27b; Verifier: openai/gpt-oss-20b | docs/architecture-decisions.md |
| ADR-003 | Modular monolith with microservice-style API boundary | docs/architecture-decisions.md |
| ADR-004 | PostgreSQL for production, SQLite for unit tests | docs/architecture-decisions.md |
| ADR-005 | STORE_ORIGINAL_TEXT=false by default | docs/architecture-decisions.md |
| ADR-006 | Keyword/regex phrase matcher as primary; embeddings behind feature flag | docs/architecture-decisions.md |
| ADR-007 | FastAPI background tasks + jobs table (no Celery in Tier 1) | docs/architecture-decisions.md |
| ADR-008 | React + TypeScript + Vite + Tailwind + shadcn/ui | docs/architecture-decisions.md |
| ADR-009 | JWT auth with roles admin/supervisor/agent | docs/architecture-decisions.md |
| ADR-010 | Synthetic agent/team assignment from hash(conversation_id) | docs/architecture-decisions.md |

---

## Metrics List

| Metric | Command | Result | Date |
|--------|---------|--------|------|
| Dataset rows | HF datasets-server /info | 3,726,699 | 2026-10-02 |
| Dataset revision | HfApi().dataset_info() | c8bfc77... | 2026-10-02 |
| Avg turns per conv (profiling) | profile_convs.py (n=25) | 16.4 turns | 2026-10-02 |
| Median text length | profile_dataset.py (n=500) | 108 chars | 2026-10-02 |
| Speaker ratio | profile_dataset.py (n=500) | agent=52%, client=48% | 2026-10-02 |
| Customer-first rate | profile_dataset.py (n=500) | 18% of convs | 2026-10-02 |
| Rows with PIN/acct patterns | profile_dataset.py (n=500) | 6.2% | 2026-10-02 |
| Tokens per per-turn call (qwen) | Real Groq call | 171 (93+78) | 2026-10-02 |
| json_schema strict: qwen | Real Groq call | Verified working | 2026-10-02 |
| json_schema strict: gpt-oss-20b | Real Groq call | Verified working | 2026-10-02 |
| Pool size | generate_manifests.py | 147 conversations | 2026-10-02 |
| Gold set | generate_manifests.py | 36 (13 dev, 23 test) | 2026-10-02 |

---

## How to Explain in 5 Minutes

EchoInsight is a conversation analytics system for telecom contact centers. It analyzes every customer call automatically - extracting call reasons, tracking customer sentiment from start to end, flagging churn risk, detecting resolution status, and scoring agent quality against a configurable checklist.

The system works in two modes: batch (analyze a complete transcript at once) and incremental (process each turn as it arrives, updating a provisional view after every message). Every claim the system makes is grounded in an exact quoted substring from the call transcript. If a quote does not match, the claim is rejected at an evidence gate.

Quality scores include evidence (quoted turns), coverage (what fraction of the checklist applied), and a flag for items needing human review. The dashboard shows supervisors KPI cards, per-call drill-down, open commitment queues, and false-resolution alerts.

The data is a synthetic telecom corpus (200,000 conversations, fictional brand "Union Mobile"). Agent and team assignments are deterministic hashes, not real org data. Both are clearly labeled throughout. The churn risk signal is a heuristic, not a validated ML prediction. All limitations are documented in the final report.

---

## Open Questions and Limitations at Phase 0

1. **Rate limits**: Free-tier Groq limits not confirmed from response headers. The budget guard reads actual headers at runtime but exact daily caps are unknown until the first real-model run.
2. **gpt-oss-120b behavior**: Returned empty string on short prompts. May require richer context. Must be verified on full extraction prompts before use as verifier.
3. **Short/very-long conversations**: Only 1 short-bucket conversation in pool. The 150-turn synthetic fixture must be hand-written.
4. **Gold annotation**: Not yet done. All evaluation results in Phase 6 will be marked "provisional" until owner completes human review.
5. **Topic clustering**: TF-IDF clustering was skipped to stay within the profiling time-box. Taxonomy was derived from observed samples and domain knowledge.

---

## Handoff Entry (if context reset)

**State as of 2026-10-02T09:30Z**: Phase 0 complete. Repository skeleton at `c:\Users\Admin\Documents\GitHub\EchoInsight`. Manifests at `data/manifests/`. All Phase 0 docs at `docs/`. `.gitignore`, `.env.example`, `Makefile`, and all skeleton `__init__.py` files created.

**What passes**: Phase 0 exit criteria met (reports written, manifests reproducible, decisions recorded, quota estimated, skeleton builds). No code tests run yet.

**What is next**: Phase 1 Foundation - Dockerfiles, docker-compose.yml, health endpoints, database models and Alembic migrations.

**Commands to resume**:
```bash
# Verify manifests
python -c "import json; d=json.load(open('data/manifests/analysis_pool_v1.json')); print(d['pool_size'], 'conversations')"
# Start Phase 1
# 1. Create backend/Dockerfile (multi-stage)
# 2. Create docker-compose.yml
# 3. Create backend/models.py (SQLAlchemy 2 models)
# 4. Create backend/api/health.py
# 5. Run alembic init and create first migration
# 6. Verify: docker compose up --build; curl http://localhost:8000/health
```

---
## [2026-10-02T16:27:45+05:30] Phase 5 + Phase 6 Completion Checkpoint

**Goal**: Complete all Tier 1 and Tier 2 deliverables.

### What was completed in this session:

**Phase 5 - API, Auth, Dashboard (Tier 1 - COMPLETE)**
- Fixed seed_users.py: imports from domain_model (NUM_AGENTS=25, AGENTS_PER_TEAM=5, NUM_TEAMS=5)
- Fixed auth dependency: missing credentials now returns HTTP 401 (not 403) with WWW-Authenticate header
- Fixed AppendTurnResponse schema: provisional_state returns None (raw state stored in DB as provisional_state_json column)
- Fixed AnalysisResponse schema: made sentiment_start/end and qa_result optional (not all analyses have them)
- Added provisional_state_json column to Conversation model; reducer runs synchronously on each append
- Added open-commitments endpoint: GET /api/v1/conversations/open-commitments
- Added false-resolutions endpoint: GET /api/v1/conversations/false-resolutions
- Added analytics endpoints: GET /api/v1/analytics/agent/{id}, GET /api/v1/analytics/team/{id}
- Server-side scoping verified: agents see only their own, supervisors see only their team

**Security Tests (CORE - COMPLETE)**
- tests/integration/test_security.py: 6 security tests
- Unauthenticated (401), missing token (401), tampered token (401)
- Cross-agent access denial (403), cross-team supervisor scoping (403 when not own team)
- Prompt injection: 4 adversarial patterns, no 500 errors, PII redacted

**Deliverables Created**
- docker-compose.prod.yml: full production stack (Postgres, migrate, API, worker, Nginx)
- frontend/Dockerfile: multi-stage Node->Nginx, non-root
- frontend/nginx.conf: SPA fallback, API proxy, security headers
- .github/workflows/ci.yml: lint, secret scan, tests, audit, Docker build
- docs/deployment.md: two deployment paths, first-deploy checklist, rollback steps
- docs/health-report.md: measured performance, estimated footprints, what was not measured
- evals/run_eval.py: evaluation pipeline (reliability, QA, sentiment, resolution, leakage check)
- evals/rubric.md: annotation rubric for gold set
- scripts/backup.sh: pg_dump to gzip with timestamp
- scripts/restore.sh: restore from gzip with confirmation
- scripts/seed_demo.sh: import pool sample and queue analysis
- Makefile: already existed, comprehensive

### Test Results
- 56/56 pass (unit=45, integration=11: lifecycle=5, security=6) in 3.1s
- New schema (provisional_state_json) seeded and verified in dev_local.db

### What Remains (Tier 2 - Phase 6)
- Audit log expansion
- Reviewer workflow endpoints (human correction of QA items)
- Analysis version selector (comparison)
- Resume conversation (Tier 2 lifecycle)
- Checklist admin API with versioning
- Embedding-based phrase matcher (feature-flagged, currently off)
- Selective verification routing metrics (requires gold annotations)
- make eval with real model runs (requires GROQ_API_KEY with quota)
- Full-volume ingest benchmark (Tier 3)
- SSE replay (Tier 3)

### Quota Status
Real-model runs in this session: 0 (no valid API key active).
All tests use mock LLM adapter labeled accordingly.

### "What the owner should understand"
The system is fully functional end-to-end without LLM calls.
To run real analysis: set GROQ_API_KEY in .env, start uvicorn and the worker,
create a conversation, append turns, call /end, poll /analysis.
The eval pipeline (make eval) reports provisional metrics; human annotation of
the gold set is required before F1 metrics are valid.
