# EchoInsight Architecture Documentation Report

This report summarizes the outputs of the architecture diagramming and documentation task, and verifies the consistency of the produced artifacts against the codebase.

## 1. Diagrams Produced

16 diagrams were generated in both `.svg` and `.png` (high-res) formats, along with a master `.docx` bundle.

* `D0_master_poster`
* `D1_system_context`
* `D2_runtime_containers`
* `D3_backend_components`
* `D4_analysis_pipeline`
* `D5_state_machine`
* `D6_commitment_ledger`
* `D7_qa_scoring`
* `D8_sequence_diagrams`
* `D9_data_model`
* `D10_security`
* `D11_deployment`
* `D12_observability`
* `D13_frontend`
* `D14_optional_layers`
* `D15_scale_out` (Design target)

**Bundles:**
* `EchoInsight_Architecture_Diagram_Pack.docx` containing all 16 diagrams with captions and step tables.

## 2. Verification Results

**Components marked `partial`, `flagged-off`, or `future`:**
- `action_layer`: Feature-flagged off (`ACTION_LAYER_ENABLED=false`). Mentioned in D3, D14.
- `assistant`: Implemented and active, but restricted to read-only DB access.
- `cases`: Marked partial (lacks a detail view, open bug D22).
- `checklist manager`: Marked partial (admin UI shows 0 items, open bug D17).
- `D15_scale_out`: Entire diagram is marked as a "future" design target (Celery, Redis, CDN, Load Balancer are not implemented).

**Gaps Found (Not fixed during documentation):**
- **D12_observability**: The F1 score and precision/recall evaluation cannot be computed because the `gold_workbook.csv` is not yet annotated by a human. Load testing has not been run. 
- **In-process limits**: Token budget and rate limiters are in-process variables, meaning they do not scale across multiple workers or restarts (D11, D15).
- **Frontend State Bug**: The Live Demo page fails to update the provisional state and ledger correctly (Bug D20).
- **Ephemeral Storage**: Render free-tier loses `demo_seed.db`. Required the `SEED_DEMO_DATA=true` workaround (documented in D11).

## 3. Peer-Review Notes (Simulated)

*Simulating a reviewer seeing the Master Poster (D0) for the first time:*

**60-Second Explanation:**
"EchoInsight is a telecom intelligence app. Users (Agents, Supervisors, Admins) log into a React SPA hosted on Vercel. The backend is a FastAPI monolith on Render with PostgreSQL. When a call transcript is ingested, it immediately hits a redaction boundary (PII scrubbed via regex) before being saved. A background worker then orchestrates LLM calls (via Groq/OpenRouter) to extract QA scores, commitments, and call reasons. Crucially, there is an 'Evidence Gate' that prevents the LLM from hallucinating quotes—every quote is substring-checked against the redacted transcript. It also features standard observability like token budgets and Prometheus metrics."

**Five Questions the Poster Answers:**
1. What data is sent to the LLM? *(Redacted text only)*
2. What prevents the LLM from making up quotes? *(The Evidence Gate)*
3. What happens if the database is empty on boot? *(demo_seed.db is restored)*
4. Which steps use the LLM vs deterministic code? *(LLM: Turn extraction, Final Analysis, QA Scoring, Selective Verify. Code: Redaction, Reducer, Ledger, Gates, Scorer)*
5. How is the system deployed? *(Vercel for frontend, Render Docker for backend, Render Postgres for DB)*

**Five Questions the Poster Does NOT Answer:**
1. What are the specific 9 regex patterns used for redaction? (Needs code dive)
2. How does the QA score math actually work? (Answered in D7)
3. What is the schema of the PostgreSQL database? (Answered in D9)
4. How is long-call windowing handled for calls >40 turns? (Answered in D4)
5. What are the exact roles and permissions for a Supervisor? (Answered in D10)

## 4. Un-run Metrics

The following metrics were explicitly marked as "Not run" in `SYSTEM_HEALTH_EVALS.md` to maintain strict honesty about the project's current state:
- **Throughput (RPS)**: Requires `locust` load test.
- **Error Rate / Rate-limit Counts**: Requires production traffic/logs.
- **Evidence-mismatch Rate**: Requires DB query on `false_resolution` after bulk evaluation.
- **F1 Score / Accuracy**: Requires human annotation of `gold_workbook.csv`.

## 5. Submission Deliverable Readiness

| Deliverable | Status | Location |
| :--- | :--- | :--- |
| **Architecture Diagram Pack** | Ready | `docs/architecture/EchoInsight_Architecture_Diagram_Pack.docx` |
| **Full Executable Code** | Ready | Entire GitHub repository. |
| **Additional Exploration** | Ready | `docs/submission/ADDITIONAL_EXPLORATION.md` |
| **System Health Evals** | Partial | `docs/submission/SYSTEM_HEALTH_EVALS.md` (F1 metrics blocked by data) |
| **Dataset Note** | Ready | Noted in `docs/architecture-decisions.md` (ADR-001) |
