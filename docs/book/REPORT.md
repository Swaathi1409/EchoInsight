# docs/book/REPORT.md
# EchoInsight Documentation Generation Report
# Generated: 2026-10-06 12:29

## Output Files

| Volume | Path | Status |
|--------|------|--------|
| Vol 1 | C:\Users\Admin\Documents\GitHub\EchoInsight\docs\EchoInsight_Vol1_Project_Documentation.docx | Generated |
| Vol 2 | C:\Users\Admin\Documents\GitHub\EchoInsight\docs\EchoInsight_Vol2_Code_Walkthrough.docx | Generated |
| Vol 3 | C:\Users\Admin\Documents\GitHub\EchoInsight\docs\EchoInsight_Vol3_Setup_Run_and_Deployment_Guide.docx | Generated |
| Vol 4 | C:\Users\Admin\Documents\GitHub\EchoInsight\docs\EchoInsight_Vol4_Viva_and_Defense_Handbook.docx | Generated |

## Coverage Summary

- Backend files covered: 60+ (all modules inventoried)
- Frontend files covered: 15+ (all key components)
- Test files covered: 13
- ADRs covered: 10
- Features traced: 10+ (ingestion, redaction, QA, verification, commitments, auth, analytics, cases, action layer, assistant)
- Questions in Vol 4 bank: 80+ grouped Q&A pairs (~200+ individual questions)
- Decisions documented: 10 full decision cards
- Algorithm deep dives: QA scoring, commitment ledger, churn risk, token budget, windowed merge, confidence normalisation

## Inferred Items (mark in documentation)

1. Tailwind CSS as styling framework — inferred from ADR-008 mention; verify in package.json
2. TanStack Query/Table installed — mentioned in ADR-008; verify in package.json
3. TypeScript in frontend — tsconfig.json observed; some .ts files; verify fully TypeScript
4. GitHub Actions CI — .github/ directory present; contents not fully enumerated
5. Per-turn extraction status prevents double-processing — documented design; verify in incremental.py
6. OpenRouter is highest priority — client.py reads openrouter_api_key first; confirmed from source

## Gaps Found in Project

1. Gold annotations missing — evals/gold_workbook.csv exists but is empty; F1 metrics cannot be computed
2. 23 open bugs (D1-D23) — all in Open status in bug-report.md; none fixed in current snapshot
3. prompts/ directory is empty — all prompts live in backend/llm/prompts.py
4. docs/screenshots/ directory is empty — no UI screenshots available for embedding
5. Eval result sample_size=0 — no live analyses available at eval time; all metrics are provisional
6. state_events table has 0 rows in demo seed — table exists but append-only log not populated by current pipeline
7. analytics/ backend package has only __init__.py — analytics routes live in api/metrics.py (slight naming inconsistency)
8. act_rules_version table has 0 rows in demo seed — table exists but rules versioning not active

## Verification Status

All code excerpts verified against source files at referenced line numbers.
All metrics cited with source; provisional/estimated clearly marked.
No placeholder text in any volume.
