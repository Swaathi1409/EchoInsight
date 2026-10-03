# EchoInsight UI Enhancement - Proceedings

## Phase A: Baseline and Audit

### A1. Git Baseline
- Branch: `ui-enhancement` (created 2026-10-03)
- Tag: `pre-ui-enhancement` 
- Pushed to: https://github.com/Swaathi1409/EchoInsight

### A2. Database Backup
- SQLite DB file: `dev_local.db` (copy preserved as `dev_local.db.bak` before any destructive step)
- Not a Postgres deployment; backup = file copy

### A3. Test Suite Baseline
- Command: `python -m pytest tests/ -q --tb=short`
- Result: **143 passed, 0 failed, 1 warning**
- Warning: passlib argon2 deprecation (not a test failure)
- Time: 17.44s

### A4. Frontend Stack Audit
| Concern | Library | Notes |
|---|---|---|
| Framework | React 19 | No TypeScript in use (jsx files) |
| Bundler | Vite 8 | Dev server on port 3000 |
| Routing | Hash-based (`#/path`) | Custom in App.jsx |
| Styling | Vanilla CSS (index.css) | No Tailwind, no CSS modules |
| Charts | None currently | All analytics are text/badges |
| Icons | lucide-react 1.49 | OK per rules |
| State | useState/useCallback | No global state |
| Data fetching | fetch() via api.js | No React Query |

**Findings:** No TypeScript (pure JSX), no Tailwind, no chart library, no animation library. All styling is custom CSS variables in index.css. Stack is minimal.

### A5. Current Routes
| Hash Route | Component | Notes |
|---|---|---|
| `#/` | Dashboard.jsx (Overview tab) | KPI cards, resolution chart |
| `#/?tab=conversations` | Dashboard.jsx (Conversations tab) | Table |
| `#/?tab=commitments` | Dashboard.jsx (Open Commitments tab) | |
| `#/?tab=false-resolutions` | Dashboard.jsx (False Resolutions tab) | |
| `#/conversation/:id` | ConversationDetail.jsx | |
| `#/demo` | LiveDemo.jsx | Scripted + manual turns |
| `#/admin` | AdminPanel.jsx | Budget, Audit, Checklists, Cases |

### A6. Database Row Counts (Baseline)
| Table | Count |
|---|---|
| conversations | 44 (but queries show 63 - likely includes soft-deleted or joined) |
| conversations (active) | 4 |
| conversations (ended) | 37 |
| conversations (closed) | 2 |
| conversations (created) | 1 |
| analyses | 54 |
| analyses (final, non-provisional) | 54 with resolution |
| qa_results | 54 |
| commitments | 66 |
| commitments (completed) | 37 |
| commitments (scheduled) | 25 |
| commitments (uncertain) | 4 |
| turns | 231 |
| users | 4 |
| agents | 25 |
| teams | 5 |
| cases | 7 |
| audit_log | 83 |
| reviews (table) | **DOES NOT EXIST** - reviews stored elsewhere |

### A7. Analysis Distribution
- resolved: 37, unresolved: 16, escalated: 1 (from non-provisional analyses)
- QA avg score: 74.6, min: 13.3, max: 100.0
- **D1 confirmed**: Dashboard shows 100% "unknown" while DB has real resolution data

### A8. Top Call Reasons (from DB)
1. billing_dispute: 22
2. internet_or_broadband_outage: 19
3. cancellation_or_churn_intent: 15
4. network_coverage_or_dropped_calls: 12
5. general_inquiry: 5

**D2 confirmed**: Reasons exist in DB but dashboard shows "No analysis data"

### A9. Reviews Table
- No `reviews` table exists. Reviews stored in a different table or column.
- `review_annotations` or embedded in `qa_results`? TBD - needs investigation.

---

## Defect Verification Status

| Defect | Reproduced | Root Cause | Files |
|---|---|---|---|
| D1 | YES | Dashboard reads wrong field or no join to analyses table | Dashboard.jsx |
| D2 | YES | Same as D1 - reasons not read from analyses | Dashboard.jsx |
| D3 | TBD | Need to verify counting logic | Dashboard.jsx |
| D4 | TBD | Need to check commitments for conv bd6f90b7 | Backend |
| D5 | TBD | scheduled:25, but open commitments all scheduled | Backend |
| D13 | YES | ConversationDetail shows no agent/team/date fields | ConversationDetail.jsx |
| D16 | YES | No reviews table found | Backend + Frontend |
| D20 | TBD | LiveDemo needs inspection | LiveDemo.jsx |

---

## What the Owner Should Understand
The frontend currently has NO chart library and very limited analytics rendering. The "Overview" page reads analytics from the API but the API may be returning incorrectly computed aggregates (D1, D2). The reviews table does not exist as a standalone entity - this is a critical gap for D16.

The core backend pipeline is solid: 143 tests pass, analyses exist with correct data in DB, provisional state works per our E2E testing. The UI layer needs significant work.

---

*Updated: 2026-10-03*
