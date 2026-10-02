# Evaluation Framework

This document describes how EchoInsight evaluates its own outputs, what is measured, what is not yet measured,
and what the owner must do before trusting any reported metric.

---

## Principle: Metrics Must Be Evidence-Grounded

All metrics reported by this system follow the same rule as the analysis outputs:
no metric is reported without a stated sample size, method, and limitation.
Labels used throughout:

- **provisional** — computed but not yet human-validated
- **synthetic** — from synthetic fixtures, not real calls
- **mock** — from a mock LLM, not the real model
- **N=n** — number of real analyzed conversations behind the metric

---

## What Is Measured

### 1. QA Scorer Correctness (Unit Tests)
**Method**: 30 synthetic fixtures (`tests/fixtures/qa_fixtures.py`)
**Status**: Automated; no human review needed
**What it checks**: Given pre-labeled item results (pass/fail/N/A), does the scorer compute the correct weighted score, coverage fraction, and critical violation cap?
**Does NOT check**: Whether the LLM produces correct item results for real calls.

### 2. Reliability (Eval Pipeline)
**Method**: `make eval` (fetches stored analyses from live API)
**Metrics**:
- `needs_review_rate`: fraction of analyzed conversations where at least one QA item was flagged `needs_review`
- `false_resolution_rate`: fraction of ended conversations flagged as false resolution
**Status**: Provisional until sample size > 30 real analyzed conversations
**Limitation**: The LLM decides what to flag; no gold truth to compare against.

### 3. QA Coverage
**Method**: Average `coverage` field from stored `qa_results`
**Status**: Provisional
**Meaning**: `assessed_weight / applicable_weight` — how much of the applicable checklist was conclusively assessed (not left as `needs_review`). Target: > 0.70.
**Does NOT measure**: Whether assessed items are correct.

### 4. Sentiment / Resolution Distribution
**Method**: Count distribution from stored analyses
**Status**: Distribution only (no F1; no gold labels available)
**Limitation**: Cannot validate correctness without human annotation of the gold set.

### 5. Leakage Check
**Method**: Automated scan for test-split IDs appearing in prompt/config/fixture files
**Status**: Automated; runs in `make eval` and in `tests/unit/test_leakage.py`
**Result**: Pass/fail per run.

---

## What Is NOT Yet Measured (and Why)

| Metric | Reason Not Computed |
|--------|-------------------|
| Call reason F1 | No gold labels — requires human annotation of `evals/gold_workbook.csv` using `evals/rubric.md` |
| Sentiment F1 (per turn) | No gold labels |
| Resolution accuracy | No gold labels |
| Evidence correctness | Requires human reading of quotes against transcript; cannot be automated |
| Provisional-vs-final agreement | Requires incremental run log paired with final analysis (Tier 2 feature) |
| Selective verification routing precision | Requires manual review of routed items per spec §5 |
| End-to-end latency (p50/p95) | Requires load test with real LLM key and running containers |
| LLM output quality on real calls | Requires GROQ_API_KEY, worker running, and gold annotation |

---

## How to Complete the Evaluation

### Step 1: Build the Gold Set (Required for F1 Metrics)

1. Select 40 conversations from `data/manifests/gold_split_v1.json` (15 dev + 25 test).
2. Open `evals/gold_workbook.csv` (to be created after running `make eval` with real analyses).
3. Annotate each conversation using `evals/rubric.md`:
   - Call reasons (multi-label)
   - Sentiment per turn
   - Resolution status
   - QA item results with evidence quotes
   - False resolution flag
4. Mark each item `confirmed` or `corrected` in the workbook.
5. Run `make eval` — F1 metrics will be computed automatically once gold labels are present.

### Step 2: Run Real-Model Analysis

```bash
# Start the worker with a real key
GROQ_API_KEY=gsk_your_key_here python -m backend.worker.main

# Submit conversations (e.g., 20 from the pool)
bash scripts/seed_demo.sh 20

# Wait for jobs to complete, then run eval
make eval
```

### Step 3: Interpret Results

- All metrics in `evals/results/eval_YYYYMMDDTHHMMSSZ.json` are labeled with sample size.
- Metrics without gold labels report distributions only; do not report them as "accuracy".
- After human annotation, re-run `make eval` to compute F1 metrics against the test split.

---

## Gold Set Split Rules

| Split | Size | Purpose |
|-------|------|---------|
| Development (dev) | 15 | Prompt tuning, threshold calibration |
| Test | 25 | Final metric reporting only |

**Critical rule**: Test split IDs must never appear in prompt files, configuration, or fixture data.
An automated check (`tests/unit/test_leakage.py`) enforces this on every test run.

---

## Model Selection Impact on Metrics

The LLM model can be changed without code changes:
```bash
LLM_PRIMARY_MODEL=your-model-here
LLM_VERIFIER_MODEL=your-verifier-model
```

All metrics must be re-computed from scratch when the model changes. Analysis results in the DB are associated with the model that produced them (`analysis.model` field). Do not mix results from different models in the same evaluation unless you segment by model.

---

## Limitations to Report

Before publishing any metric from this system, state:

1. Sample size (N)
2. Whether the metric is from real calls or synthetic fixtures
3. Whether the metric has been validated against human annotations
4. The model that produced the analyzed results
5. Whether the gold set is human-reviewed or LLM pre-annotated

Do not report F1 scores from LLM pre-annotation without human review — pre-annotated labels are not ground truth.

---

## Running the Evaluation

```bash
# Full eval (fetches from live API, saves to evals/results/)
make eval

# Output location
ls evals/results/

# JSON report fields
cat evals/results/eval_YYYYMMDDTHHMMSSZ.json
```
