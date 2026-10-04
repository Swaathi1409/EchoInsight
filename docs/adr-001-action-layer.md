# ADR-001: Action Layer Architecture Decisions

## Status: Accepted

## Date: 2026-10-03

## Context

We are adding an optional Action Intelligence Layer on top of EchoInsight's existing
conversation analysis. This ADR records the key architecture decisions made at the
start of Phase 0 before any feature code is written.

---

## Decision 1: As-Of Clock

**Decision:** The as-of clock for the dataset pool is the latest `started_at` timestamp
in the conversations table. At time of baseline capture this is `2026-10-03 09:57:27 UTC`
(labeled "Evaluated as of 3 Oct 2026 09:57 (data clock)" on all time-sensitive screens).
For live/manual conversations the as-of clock is wall-clock time. The clock source is
stored in `act_settings.as_of_mode` (`dataset_max | realtime | manual`) and is
admin-configurable at runtime. Every time-sensitive screen shows the as-of value
and its mode.

**Alternatives considered:**
- Always use real wall-clock: rejected — the entire dataset predates now, every commitment
  would show as "overdue", making the overdue flag meaningless.
- Use the median call date: rejected — less intuitive than the max, harder to explain.

**Consequence:** Overdue calculations, urgency flags, and PDCA windows are all evaluated
relative to `as_of`, not real-now. Workflow timestamps (claimed, contacted, closed) are
still wall-clock because they represent operator actions in real time.

---

## Decision 2: Package Structure

**Decision:** New code lives exclusively in `backend/action_layer/` and `frontend/src/action_layer/`.
All new DB tables use the `act_` prefix. All new API routes are under `/api/v1/action/`.
No existing file in `backend/` (except `alembic/versions/`) is modified.

**Alternatives considered:**
- Add to existing backend/api/: rejected — mixing concerns, harder to disable cleanly.
- Separate microservice: rejected — too much operational overhead for this project.

---

## Decision 3: Master Switch

**Decision:** `ACTION_LAYER_ENABLED` environment variable (default `false`) AND a runtime
toggle in `act_settings.enabled` (default `false`). Both must be true for the layer to
activate. When disabled: all `/api/v1/action/` endpoints return `{"enabled": false, "detail": "Action layer is disabled"}` with HTTP 200; the derive job is a no-op; the frontend
hides the "Action Center" nav group entirely.

---

## Decision 4: Derive Job Strategy

**Decision:** Pull-based derive job (never push, never hook into the pipeline). The derive
job runs on demand (admin trigger) and on a configurable schedule (default: every hour).
It finds conversations with a final (non-provisional) analysis but no `act_item` for the
current `rules_version`. It derives deterministically from stored results only.
Re-derive is idempotent: it creates new rows marked `current=true` and marks old rows
`current=false` (history preserved, never deleted).

---

## Decision 5: Evidence Integrity

**Decision:** Reuse the existing `backend/qa/phrase_matcher.py` for quote verification.
Every risk signal that references a customer quote must pass verification. If a signal
cannot be verified against stored turn text, it is omitted and the item is flagged
`evidence_complete=false` with a specific reason. The UI shows a visible warning on
items with incomplete evidence.

---

## Decision 6: Scope Authorization

**Decision:** Centralized scope enforcement in a new `backend/action_layer/auth.py`
helper. Admins see all. Supervisors see only their `team_id`. Agents see only their
own `agent_id`. Client-supplied filters can only narrow scope further, never expand it.
Every new endpoint calls the scope helper before any query.

---

## Baseline Snapshot (Phase 0 captured 2026-10-03)

| Metric | Value |
|---|---|
| Test suite | 143 passed, 0 failed, 1 warning |
| Branch | `action-layer` (from `ui-enhancement` at `f1ad69f`) |
| Tag | `pre-action-layer` |
| DB backup | `backups/dev_local_pre_action_layer.db` |
| Conversations | 46 |
| Analyzed (final) | 38 |
| Analyses rows | 57 |
| Commitments | 68 (31 open) |
| QA results | 57 (20 critical violations) |
| False resolutions | 1 |
| Agents | 25 |
| Teams | 5 |
| Data range | 2026-10-02 10:17 to 2026-10-03 09:57 |
| As-of clock (dataset) | 2026-10-03 09:57:27 |
| Resolution breakdown | resolved: 37, unresolved: 18, escalated: 1, partially_resolved: 1 |
| Churn risk | high: 6, low: 51 |
| Golden snapshots | 15 captured |
