# EchoInsight Architecture

## Problem

Telecom contact centers review only 2% of calls manually. Quality teams have limited visibility into why customers call or how agents perform. The goal is to automatically analyze every conversation and surface actionable insights.

## High-Level Architecture

```mermaid
graph TB
    subgraph Client["Client (Browser)"]
        UI["React Dashboard\n(Vite + Tailwind + shadcn/ui)"]
    end

    subgraph API["API Layer (FastAPI)"]
        AUTH["Auth\n(JWT + argon2)"]
        APIV1["API v1 Endpoints\n(/api/v1/...)"]
        HEALTH["/health /ready /metrics"]
    end

    subgraph Backend["Backend Packages"]
        INGEST["ingest\nLoad, normalize, redact, validate"]
        ANALYSIS["analysis\nExtraction pipeline, windowing, reconciliation"]
        STATE["state\nReducer, provisional ledger, state events"]
        QA["qa\nChecklist engine, phrase matcher, coverage"]
        VALIDATOR["validator\nEvidence gate, schema validation"]
        ANALYTICS["analytics\nRollups, agent and team aggregates"]
        LLM["llm\nGroq adapter, rate limiter, budget guard"]
    end

    subgraph Worker["Worker Process"]
        JOBWORKER["Job Worker\n(same codebase, separate entrypoint)"]
    end

    subgraph Storage["Storage"]
        PG["PostgreSQL\n(conversations, turns, analyses, jobs, audit_log)"]
        JOBQ["jobs table\n(queued, running, succeeded, failed)"]
    end

    subgraph External["External"]
        GROQ["Groq API\n(qwen/qwen3.8-27b primary\nopenai/gpt-oss-20b verifier)"]
        HF["HuggingFace\n(dataset fetch only)"]
    end

    UI --> AUTH
    AUTH --> APIV1
    APIV1 --> INGEST
    APIV1 --> ANALYSIS
    APIV1 --> STATE
    APIV1 --> QA
    APIV1 --> ANALYTICS
    INGEST --> PG
    ANALYSIS --> LLM
    ANALYSIS --> VALIDATOR
    ANALYSIS --> STATE
    QA --> LLM
    QA --> VALIDATOR
    STATE --> PG
    ANALYTICS --> PG
    LLM --> GROQ
    APIV1 --> JOBQ
    JOBWORKER --> JOBQ
    JOBWORKER --> ANALYSIS
    JOBWORKER --> PG
    INGEST -.->|fetch pool| HF
```

## Package Responsibilities

| Package | Responsibility |
|---------|---------------|
| `ingest` | Load and normalize CSV/JSON input; validate columns; map `client` to `customer`; normalize whitespace; detect and flag duplicates; assign synthetic agent and team; validate turn ordering |
| `llm` | Provider-agnostic adapter interface; Groq implementation; token-bucket rate limiter; exponential backoff with jitter; daily budget guard; `Retry-After` handling; test double |
| `analysis` | Incremental (per-turn) and batch (full conversation) extraction pipelines; long-call windowing; summary, reasons, sentiment trajectory, resolution, churn signals; final reconciliation |
| `state` | Deterministic idempotent reducer; state event log; provisional and final commitment ledger; false-resolution detector; open-commitment queue |
| `qa` | QA checklist engine; keyword/regex phrase matcher; per-item scoring (pass/fail/not_applicable/needs_review); coverage calculation; selective verification hooks |
| `validator` | Evidence gate (turn ID existence + exact-quote check); schema validation; output consistency checks; error categorization; retry routing |
| `analytics` | Conversation rollups; agent and team aggregate queries; KPI computation; materialized or incremental rollup updates |
| `api` | FastAPI router; Pydantic request/response schemas; JWT auth middleware; central authorization dependency; pagination; error handlers |

## Data Flow: Incremental (Live) Mode

```mermaid
sequenceDiagram
    participant C as Client
    participant API as API
    participant INGEST as ingest
    participant LLM as llm
    participant GATE as validator
    participant RED as state/reducer
    participant DB as PostgreSQL

    C->>API: POST /api/v1/conversations/{id}/turns
    API->>INGEST: Redact turn text
    INGEST->>DB: Store redacted turn (extraction_status=pending)
    API->>LLM: Per-turn extraction (new turn + 3 context + state digest)
    LLM->>GATE: Validate JSON schema
    GATE->>GATE: Verify turn IDs exist, exact-quote match
    GATE->>RED: Apply validated events
    RED->>DB: Update provisional state + ledger (idempotent)
    API->>C: 200 { updated_provisional_state, ledger, turn_id }
```

## Data Flow: Batch (Final) Mode

```mermaid
sequenceDiagram
    participant C as Client
    participant API as API
    participant JOB as jobs table
    participant WORKER as Worker
    participant LLM as llm
    participant DB as PostgreSQL

    C->>API: POST /api/v1/conversations/{id}/end
    API->>DB: Set status=ended
    API->>JOB: Enqueue final_analysis job
    API->>C: 202 { job_id }
    WORKER->>JOB: Dequeue job
    WORKER->>LLM: Full extraction (windowed if >40 turns)
    WORKER->>DB: Store final analysis (analysis_version++)
    WORKER->>DB: Reconcile provisional vs final state
    WORKER->>JOB: Mark job succeeded
    C->>API: GET /api/v1/conversations/{id}/analysis
    API->>C: 200 { analysis, provisional=false }
```

## Security Boundary

- All endpoints except `/health`, `/ready`, and `/api/v1/auth/login` require a valid JWT.
- Authorization scope (which conversations an agent or supervisor can see) is derived server-side from the authenticated user's team and agent membership in the database.
- Client-supplied `team_id` or `agent_id` may only narrow results within the caller's own scope, never widen it.
- Transcripts sent to Groq are redacted. Original text is never stored or transmitted.

## Deployment Topology (Production)

```mermaid
graph LR
    PROXY["nginx reverse proxy\n(static frontend + API proxy)"]
    API["api container\n(FastAPI, non-root)"]
    WORKER["worker container\n(job processor, non-root)"]
    DB["postgres container\n(named volume)"]

    PROXY --> API
    API --> DB
    WORKER --> DB
```

## Key Design Choices

- **Modular monolith**: Easier to test and deploy than microservices for MVP; clear path to extraction if needed.
- **Idempotent reducer**: All state changes are keyed by (conversation_id, turn_id, event_type, target). Replaying or retrying never creates duplicate ledger entries.
- **Evidence gate**: Every LLM output claim must be backed by a verifiable quote. This is the primary reliability guarantee.
- **Coverage metric**: QA scores are always reported with coverage so a high score from a small applicable subset is never misleading.
- **Selective verification**: Verification calls are targeted (high-risk claims only) to preserve quota.
- **Provisional badges**: Incremental state is clearly labeled `provisional=true` in storage, API, and UI until finalized.
