# EchoInsight Architecture Narrative

EchoInsight is a telecom conversation intelligence platform designed to ingest call transcripts, run deterministic redactions and exact-quote validations, and use LLMs to extract structural analysis (resolutions, QA scores, and commitment ledgers). 

This document provides a complete narrative of the system's design, embedded with the generated architecture diagrams, linking decisions directly to the code.

## 1. High-Level Master Architecture

EchoInsight is built as a **Modular Monolith** [ADR-003](file:///docs/architecture-decisions.md) with a microservice-style boundary. 
The system runs as a stateless API with an out-of-band worker process, backed by PostgreSQL. 

![D0 Master Poster](diagrams/D0_master_poster.svg)

**How to read this diagram:**
- **Blue boxes** represent deterministic code (Python logic).
- **Orange boxes** represent LLM inference boundaries.
- **Red diamonds** represent deterministic validation gates (e.g., substring matching).
- **Green cylinders** represent data persistence.

## 2. System Context

Who uses EchoInsight, and what external systems does it rely on?

![D1 System Context](diagrams/D1_system_context.svg)

EchoInsight has three roles (Admin, Supervisor, Agent). It relies on Vercel for frontend hosting and Render for backend hosting. For intelligence, it calls Groq (or OpenRouter) via OpenAI-compatible REST APIs. 

## 3. Runtime Containers & Deployment

The application is deployed on Render's free tier. 

![D2 Runtime Containers](diagrams/D2_runtime_containers.svg)
![D11 Deployment](diagrams/D11_deployment.svg)

### Boot Sequence and Ephemeral Storage
Render's free tier scales to zero after 15 minutes of inactivity. When it wakes up:
1. `alembic upgrade head` ensures schema parity.
2. Checklists are seeded from YAML (`backend/bootstrap.py`).
3. If `SEED_DEMO_DATA=true` (which is required on Render), it seeds a deterministic demo state. This is because Render free tier has an ephemeral filesystem, so the static `demo_seed.db` SQLite snapshot cannot be used natively without copying data into PostgreSQL.

## 4. Backend Components

The backend enforces strict dependency layers to prevent circular imports. 

![D3 Backend Components](diagrams/D3_backend_components.svg)

- The `models` package sits at the bottom (all state definitions).
- The `api` and `worker` packages sit at the top.
- The intelligence happens in `analysis`, `qa`, and `validator`.

## 5. The Analysis Pipeline

The system processes data in two phases: **Incremental (Per-turn)** and **Final (On End)**.

![D4 Analysis Pipeline](diagrams/D4_analysis_pipeline.svg)
![D8 Sequence Diagrams](diagrams/D8_sequence_diagrams.svg)

### Redaction First [ADR-005]
When a turn arrives, it immediately passes through `ingest/redactor.py`, which uses 9 regex patterns to replace PII with tags (e.g., `[CARD]`). The original text is immediately discarded and **never** stored, logged, or sent to the LLM. 

### Final Analysis
When the call ends, a `final_analysis` job is queued. The pipeline orchestrates:
1. Long-call windowing (chunking by 40 turns).
2. Primary LLM call for summary, resolution, and commitments.
3. QA LLM call for 6 checklist items.
4. Deterministic gates (Evidence Gate + Hard Gate).

## 6. QA Scoring and Evidence Gates

EchoInsight refuses to trust the LLM implicitly.

![D7 QA Scoring Flow](diagrams/D7_qa_scoring.svg)

1. **Evidence Gate**: `validator/evidence_gate.py` asserts that every quote returned by the LLM is an exact substring of the *redacted* transcript. Hallucinated quotes result in a `needs_review` flag.
2. **Deterministic Fallbacks**: `qa/phrase_matcher.py` uses regex for basic items (e.g., greetings). If the LLM misses it, the code overrides it.
3. **Selective Verification**: `qa/verification.py` routes low-confidence, critical, or controversial items to a *second* LLM (ideally a different model family) for a second opinion.
4. **Critical Violations**: If a critical item (e.g., Identity Verification) fails, the conversation score is hard-capped at 60 (`qa/scorer.py`).

## 7. Data Model and Ledger

The commitment ledger tracks promises made during a call.

![D9 Data Model](diagrams/D9_data_model.svg)
![D6 Commitment Ledger](diagrams/D6_commitment_ledger.svg)

*Note on D4 bug fix:* During final analysis, provisional commitments (created during incremental analysis) are completely deleted and replaced to avoid duplicates.

## 8. State and Lifecycle

![D5 State Machine](diagrams/D5_state_machine.svg)

The background worker (`worker/main.py`) polls the DB every 5 seconds for jobs. It also runs an idle sweep (marking active calls ended if no turns arrive for 30 minutes) and a closure sweep (archiving calls after 72 hours).

## 9. Security & Trust Boundaries

![D10 Security & Trust Boundaries](diagrams/D10_security.svg)

- **Auth**: JWT via `backend/auth.py` (30m expiry).
- **RBAC Scope**: Scope is applied at the database query level by `get_current_user` in `backend/api/deps.py`. It is impossible for an agent to widen their scope via URL parameters.
- **Prompt Injection Defense**: Explicit `<transcript>` XML tags and strong system instructions.

## 10. Observability and Testing

![D12 Observability](diagrams/D12_observability.svg)

- **Metrics**: Standard `/health` and Prometheus `/metrics`.
- **Token Budget**: An in-process counter resets daily to prevent cost blowouts.
- **Audit Log**: High-risk actions are written to `audit_log`.

## 11. Frontend Architecture

![D13 Frontend Architecture](diagrams/D13_frontend.svg)

A Vite-built React SPA, using TanStack Query for state and shadcn/ui for components.

## 12. Optional Layers

![D14 Optional Layers](diagrams/D14_optional_layers.svg)

Features like the Action Layer (PDCA engine) are feature-flagged off (`ACTION_LAYER_ENABLED=false`). The Assistant operates in a read-only mode, executing tools safely without mutating the transcript.

## 13. Scale-Out Target (Future Design)

What happens when we move beyond the free tier?

![D15 Scale-Out Target](diagrams/D15_scale_out.svg)

**Key scaling changes:**
1. Move the jobs table queue to Celery + Redis.
2. Move the in-process rate limiter and token budget to Redis (to support multiple replicas).
3. Scale the FastAPI service horizontally behind a load balancer.

## Deterministic vs. LLM Task Distribution

| Task | Type | Module | Why |
| :--- | :--- | :--- | :--- |
| PII Redaction | Deterministic | `ingest/redactor.py` | Must be 100% reliable before storage |
| Evidence Gate | Deterministic | `validator/evidence_gate.py` | LLMs hallucinate quotes; code does not |
| State Merging | Deterministic | `state/reducer.py` | Pure functional merge is safer than LLM JSON patching |
| Phrase Matching | Deterministic | `qa/phrase_matcher.py` | Regex is cheaper and 100% reliable for fixed scripts |
| Turn Extraction | LLM (qwen) | `analysis/incremental.py` | Needs semantic understanding of intent |
| Final QA Scoring | LLM (qwen) | `analysis/pipeline.py` | Complex reasoning required (e.g. empathy) |
| Selective Verify | LLM (gpt) | `qa/verification.py` | Second opinion on ambiguous items |

## Known Limitations and Gaps

- The token budget and rate limiters are in-process. They will not function correctly if the API is scaled to >1 instance.
- Render's free tier spins down after 15 minutes, causing a 30-60s cold start.
- `STORE_ORIGINAL_TEXT` is false by default. Exact-quote validation strictly compares against the *redacted* text.
- Token refresh and token revocation blocklists are not implemented.
- F1 evaluation metrics cannot be computed until the `gold_workbook.csv` is annotated by a human.
