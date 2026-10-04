# Phase 0 Audit and Preflight

## 1. Baseline Counts & Tests
- **Branch created**: `checklist-cases`
- **Tag created**: `pre-checklist-cases`
- **Database Backup**: Stored in `.backup/dev_local_pre_checklist_cases.db`
- **Tests**: `pytest tests/` passed (259 passed, 1 warning in ~21s)

**Table Row Counts**:
- _test_lock: 0
- act_drafts: 152
- act_initiative_events: 10
- act_initiatives: 9
- act_item_events: 155
- act_items: 152
- act_prevention_suggestions: 12
- act_recommendations: 402
- act_recurring_issues: 8
- act_rules_version: 0
- act_settings: 1
- agents: 25
- alembic_version: 1
- analyses: 57
- asst_feedback: 15
- asst_message: 248
- asst_session: 79
- asst_settings: 1
- audit_log: 277
- case_conversations: 9
- cases: 8
- commitments: 68
- conversations: 49
- jobs: 92
- qa_results: 57
- review_annotations: 1
- segments: 14
- state_events: 0
- teams: 5
- turns: 264
- users: 5

## 2. API Golden Snapshots
- Captured 15 conversations and analytics overview.
- Saved in `.backup/golden_snapshots.json`.
- Latencies: p50: 2051.91 ms, p95: 2064.76 ms.


## HANDOFF to New Session

**Current State:**
- Phase A (Audit and Baseline) is complete.
- Baseline backup created at .backup/dev_local_baseline.db.
- Full pytest suite ran: 6 failures (all related to new QA rules testing in 	est_qa_fixtures.py and 	est_qa_scorer.py), 253 passed.
- Golden API snapshots captured via scripts/capture_baseline.py to .backup/golden_snapshots.json.
- UI Screenshots captured across themes and viewports via scripts/capture_screenshots.py.
- docs/audit-final.md and docs/seed-coverage.md have been initialized and filled with the audit results.

**Next Steps:**
- Proceed to Phase B: Full Bug Sweep and Fixes.
- Read docs/audit-final.md and docs/seed-coverage.md to get context.
- Triage the 6 test failures in QA scorer tests.
- Follow the bug fixes laid out in section 4.2 of the final prompt (D1 through D23).

**Commands to run next:**
- pytest (to verify the 6 failing tests again).
- Create docs/bug-report.md to track fixes.
