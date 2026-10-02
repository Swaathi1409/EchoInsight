# Problem Analysis

## Context

Telecom contact centers receive thousands of customer calls daily. Quality teams currently review approximately 2% of calls manually, creating blind spots:
- Supervisors cannot identify systemic issues (recurring network problems, billing disputes) without sampling bias.
- Agent performance is evaluated on a small, potentially unrepresentative subset.
- Compliance violations (prohibited promises, missing disclosures) may go undetected in 98% of calls.
- Follow-up commitments made during calls (promised callbacks, scheduled visits) are tracked manually or not at all.

## Assignment Requirements

Build a simple microservice that:

1. **Accepts a call transcript** (or chat log) and produces:
   - Concise summary
   - Call reasons (multi-label)
   - Customer sentiment across the call (start to end)
   - Resolution status
   - Churn-risk flag
   - Follow-up actions (live, updated after every turn)

2. **Scores agent quality** against a configurable QA checklist:
   - Greeting, identity verification, empathy, correct disclosure, no prohibited promises, proper closure
   - Evidence (quoted turns) for each score
   - Compliance violation flags
   - Roll-up to agent and team level

3. **Ensures explainability and reliability**:
   - Every claim grounded in a verifiable exact quote
   - Coverage metric on QA scores
   - Selective verification for high-risk claims
   - Controlled handling of ambiguous and adversarial inputs

## Key Challenges and How We Address Them

### 1. Output Reliability

**Problem**: LLMs can hallucinate claims not supported by the transcript.

**Solution**: The evidence gate requires every structured output claim to cite a real turn ID and an exact substring of that turn's redacted text. Claims that fail this check are rejected or routed to `needs_review`. The gate is deterministic and 100% auditable.

**Limitation**: The gate verifies that a quote exists, not that the interpretation of the quote is correct. Interpretation errors are addressed by selective verification (a second model checks the reasoning).

### 2. Incremental Processing (Live Mode)

**Problem**: A call can be long-running. Supervisors want visibility into what is happening now, not after the call ends.

**Solution**: Each appended turn triggers a lightweight per-turn extraction call. The result updates a provisional state and commitment ledger visible in real time. The provisional state is replaced by the final analysis when the call ends.

**Limitation**: Per-turn extraction uses a truncated context (new turn + 3 preceding turns + state digest). It may miss context from earlier in the call. The final analysis uses the full transcript and overrides provisional values, with differences recorded in the state timeline.

### 3. QA Scoring Coverage

**Problem**: Not all checklist items apply to every call (e.g., "greeting" is not applicable if the customer called back into a transfer). A high score from a small applicable subset can be misleading.

**Solution**: The system always computes and returns `items_applicable`, `items_assessed`, `items_needs_review`, and `coverage = assessed_weight / applicable_weight`. If coverage is below 70%, the score is marked `partial`, displayed with a visible badge, and excluded from aggregates by default.

### 4. Churn Risk

**Problem**: No outcome labels exist in the dataset. True churn probability requires historical outcome data.

**Solution**: Implement a heuristic signal-based risk level (low, medium, high) derived from observable signals: customer sentiment trajectory (worsening), unresolved issues, explicitly mentioned cancellation intent, failed resolution, repeated contacts. This is clearly labeled as a heuristic signal, never presented as a probability or validated prediction.

### 5. Redaction and Privacy

**Problem**: The dataset contains synthetic but realistic sensitive values (PINs, account numbers, masked patterns). Real deployments would have real PII.

**Solution**: Redact before any persistence, logging, embedding, or LLM call. All quotes in the UI use redacted text. Original text is never stored (STORE_ORIGINAL_TEXT=false by default). This is implemented as if the data were real, providing a production-ready pattern.

### 6. Agent and Team Data

**Problem**: The dataset has no agent IDs, team IDs, or organizational structure.

**Solution**: Deterministic synthetic assignment: `hash(conversation_id) % 25` assigns each conversation to one of 25 agents in 5 teams. Stored with `synthetic_assignment=true`. Displayed with a visible "synthetic assignment" label in all UI views and API responses. Never claimed to be real organizational data.

## Scope Decisions

### What Is In Scope (Tier 1)

- Complete transcript batch analysis
- Live incremental processing (per-turn provisional state)
- Evidence gate on all LLM outputs
- QA scoring with coverage
- Selective verification for high-risk claims
- JWT auth with roles and server-side scope enforcement
- Dashboard: overview KPIs, conversation list, conversation detail with transcript drill-down
- Configurable taxonomy and QA checklist

### What Is Deferred (Tier 2)

- Conversation resume after end
- Analysis version history
- Reviewer feedback workflow
- Audit log expansion
- Segments within a conversation
- Checklist admin UI

### What Is Stretch (Tier 3)

- Live SSE replay
- Case linking across conversations
- Load test and full-volume ingest benchmark
- Caddy HTTPS

### What Is Explicitly Not Claimed

- Real-time audio transcription (input is text only)
- Validated churn prediction (heuristic only)
- Human-reviewed gold set (prepared but owner must annotate)
- Complete security hardening (documented gaps in docs/security.md)
- Horizontal scale beyond a single Compose stack (path documented)

## Evaluation Strategy

The system is evaluated on:
- **Reliability**: Invalid-output rate, evidence-mismatch rate, share of claims blocked by the evidence gate.
- **Task accuracy**: Call reasons F1, sentiment direction agreement, resolution accuracy, QA per-item precision and recall (on gold dev set; provisional until human-reviewed).
- **Coverage**: QA coverage distribution across conversations.
- **System health**: Latency, error rate, token cost per conversation.

All metrics from real model runs are labeled with sample size. Mock-based metrics are labeled "mock". Results marked "provisional" until gold annotations are human-reviewed.
