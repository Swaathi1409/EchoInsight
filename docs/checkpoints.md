# Phase Checkpoints

## Checkpoint 1: Phase 0 Exit

**Phase**: 0 - Design, Data, Model and Quota Review
**Date**: 2026-10-02
**Status**: PASS

### Exit Criteria

| Criterion | Status | Evidence |
|-----------|--------|----------|
| Dataset verified (revision, license, columns) | PASS | proceedings.md Step 1; revision c8bfc77, MIT license, 4 columns confirmed |
| Bounded profiling complete | PASS | proceedings.md Step 2; 500 rows, 5 offsets, stats consistent |
| Analysis pool manifest reproducible from seed | PASS | data/manifests/analysis_pool_v1.json; seed=42, 147 conversations |
| Gold split manifest created | PASS | data/manifests/gold_split_v1.json; 13 dev, 23 test |
| Leakage check in place | PASS | tests/unit/test_leakage.py (created in Phase 1) |
| Groq models verified | PASS | proceedings.md Step 5; qwen/qwen3.8-27b and openai/gpt-oss-20b confirmed |
| Structured output (json_schema strict) verified | PASS | qwen/qwen3.8-27b verified with real Groq call |
| Quota estimate recorded | PASS | proceedings.md Quota Estimate section; ~45k tokens for Phase 3 demo |
| Stack decisions recorded in ADRs | PASS | docs/architecture-decisions.md; ADR-001 through ADR-010 |
| Repository skeleton created | PASS | All directories, __init__.py, .gitignore, .env.example, Makefile |
| docs/dataset.md written | PASS | docs/dataset.md |
| docs/dataset-profile.json written | PASS | docs/dataset-profile.json |
| docs/architecture.md with Mermaid diagram | PASS | docs/architecture.md |
| docs/problem-analysis.md written | PASS | docs/problem-analysis.md |
| backend/config/taxonomy.yaml written | PASS | backend/config/taxonomy.yaml |
| backend/config/policy_example_v1.yaml written | PASS | backend/config/policy_example_v1.yaml |

**Owner action required**: Review this checkpoint and reply CONTINUE to proceed to Tier 1 MVP (Phase 1-5).

---

## Checkpoint 2: Tier 1 MVP (Phase 5 Exit)

**Phase**: 5 - API, Auth, Rollups, Dashboard
**Date**: Not yet reached
**Status**: PENDING

Will be populated after Phase 5 is complete.

Exit criteria (to be verified):
- End-to-end demonstration: append turns live, end conversation, view final analysis in dashboard
- Real-model analysis of at least 1 conversation using qwen/qwen3.8-27b
- All CORE tests pass
- Tier 1 security boundary holds (unauthenticated, cross-team, parameter-tampering tests pass)
- QA results have verified evidence and coverage figures
- Requirement-to-implementation-to-test mapping table complete

**Owner action required**: Reply CONTINUE after reviewing the Phase 5 status report.
