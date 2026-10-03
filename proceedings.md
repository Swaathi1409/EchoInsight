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
| `#/demo` | LiveDemo.jsx | 3-panel live console (D20 fixed) |
| `#/admin` | AdminPanel.jsx | Budget, Audit, Checklists, Cases |

### A6. Database Row Counts (Baseline)
| Table | Count |
|---|---|
| conversations | 44 |
| analyses | 54 |
| qa_results | 54 |
| commitments | 66 |
| turns | 231 |
| users | 4 |
| agents | 25 |
| teams | 5 |
| cases | 7 |
| audit_log | 84+ |
| review_annotations | Created (D16 fix) |

---

## Phase B: Defect Fixes Completed (2026-10-03)

### B1. Summary

All non-regression tests pass: **143/143** after each change batch.

### B2. Defect Fix Log

| Defect | Status | Root Cause | Fix |
|---|---|---|---|
| D1 - Resolution shows 100% unknown | **FIXED** | API list endpoint did not return `resolution` | Added field to `ConversationSummary` schema + `_conv_summary` query; Dashboard reads `c.resolution` |
| D2 - Call reasons show no data | **FIXED** | Same - `reasons` not in list response | Added `reasons` to schema + query; Dashboard reads `c.reasons` |
| D3 - "Total Analyzed" = all convs | **FIXED** | Counted `total` not `analysis_version > 0` | Dashboard now counts `analyzed` (convs with analysis_version > 0); shows pending count |
| D6 - Deadline tag leakage | **FIXED** | Raw LLM deadline tags shown verbatim | Added `formatDeadline()` helper in ConversationDetail; raw value in tooltip |
| D9 - Verified badge on N/A items | **FIXED** | QAItem showed badge unconditionally | Badge only shown when `result !== 'not_applicable'` |
| D12 - Review form defaults Approved | **FIXED** | `reviewVerdict` initialized to `'approved'` | Now defaults to `''`; submit disabled until verdict chosen; guard in `submitReview` |
| D13 - Missing agent/team/date | **FIXED** | Header div didn't render these fields | Added agent_id, team_id, formatted date to ConversationDetail header |
| D15 - Heading hierarchy | **FIXED** | Dashboard and Admin used `<h1>` alongside sidebar h1 | Changed to `<h2>` in Dashboard and AdminPanel |
| D16 - Reviews lost on restart | **FIXED** | `_review_store` was an in-memory dict | Added `ReviewAnnotation` ORM model + SQLite table; `admin.py` persists to DB |
| D18 - Audit log raw text | **FIXED** | Raw action keys, truncated JSON, no actor, no copy | Rewrote AuditLogTable: human labels, click-to-expand drawer, User column, copy ID buttons |
| D20 - Live Demo no provisional state | **FIXED** | Append response had provisional_state but wasn't stored or displayed | Rewrote LiveDemo as 3-panel console: controls, transcript, live provisional state + commitment ledger |

### B3. Git Commits (ui-enhancement branch)
- `fix: D1/D2 resolution+reasons in list API, D6 deadline formatting, D13 agent/team/date in header, D16 persistent reviews DB table`
- `fix: D3 analyzed count, D6 deadline format, D9 no badge on N/A, D12 review requires verdict, D15 heading hierarchy`
- `fix: D18 audit log readability (human labels, drawer, copy IDs, dates), D15 heading hierarchy in Admin`
- `fix: D20 live console - 3-panel layout with real-time provisional state + commitment ledger`

### B4. Remaining Defects (Not Yet Fixed)
| Defect | Status |
|---|---|
| D4 - Duplicate commitments | Not started |
| D5 - scheduled vs open status | Not started |
| D7 - Constant 95% confidence in QA | Not started - likely in phrase_matcher |
| D10 - Action items never shown | Not started |
| D11 - Churn risk undefined | Not started |
| D14 - Sentiment always neutral | Not started |
| D17 - Checklists policy management | Not started |
| D19 - No cases detail view | Not started |
| D21 - Thin admin metrics | Not started |
| D22 - Cases no conversation links | Not started |
| D23 - Budget status mock data | Not started |

---

*Updated: 2026-10-03 (Phase B complete)*
