# EchoInsight System Health & Evals

This document catalogs the system health and evaluation metrics for the EchoInsight platform. 
As per the rules, only actually executed metrics are reported with results. Un-run metrics are explicitly marked.

## 1. System Health (Latency & Throughput)

| Metric | Result | Sample Size | Date | Command / Source |
| :--- | :--- | :--- | :--- | :--- |
| **API Latency (p50)** | 2051.91 ms | 15 snapshots | 2026-10-06 | `python scripts/capture_baseline.py` (saved in `.backup/golden_snapshots.json`) |
| **API Latency (p95)** | 2064.76 ms | 15 snapshots | 2026-10-06 | `python scripts/capture_baseline.py` (saved in `.backup/golden_snapshots.json`) |
| **Error Rate** | **Not run** | - | - | Run: `curl -s https://<prod-url>/metrics \| grep error_rate` |
| **Throughput (RPS)** | **Not run** | - | - | Load test required. Run: `locust -f load_test.py` |
| **Memory Peak** | **Not run** | - | - | Run: `docker stats` during load |
| **Cold Start Time** | ~30-60s (observed) | - | 2026-10-06 | Observed via Vercel → Render free tier wake up |

## 2. LLM Usage & Quality

| Metric | Result | Sample Size | Date | Command / Source |
| :--- | :--- | :--- | :--- | :--- |
| **Token Usage (Avg/Call)** | ~171 tokens (per turn extraction) | 1 turn | 2026-10-02 | `docs/architecture-decisions.md` (ADR-002) |
| **Rate-limit & Retry Counts** | **Not run** | - | - | Requires prod log query |
| **Evidence-mismatch Rate** | **Not run** | - | - | Run: `SELECT count(*) FROM analyses WHERE false_resolution=True;` |
| **Invalid-output Rate** | **Not run** | - | - | DB query on `jobs` table `error` column |
| **Review-routing Rate** | **Not run** | - | - | Run: `SELECT count(*) FROM qa_results WHERE score_label = 'needs_review';` |

## 3. Evaluation Pipeline (Gold Set)

| Metric | Result | Sample Size | Date | Command / Source |
| :--- | :--- | :--- | :--- | :--- |
| **Eval Execution** | Ran (empty sample) | 0 | 2026-10-02 | `evals/eval_20261002T105635Z.json` |
| **Gold Workbook Annotated** | No | 0 | - | File: `evals/gold_workbook.csv` requires human annotation |
| **F1 Score / Accuracy** | **Not run** | - | - | Run `make eval` AFTER annotating the gold workbook |

## 4. Test and CI Status

| Metric | Result | Sample Size | Date | Command / Source |
| :--- | :--- | :--- | :--- | :--- |
| **Phase 0 Baseline Tests** | 259 passed, 1 warning | 260 tests | 2026-10-06 | `pytest tests/` (from `proceedings.md`) |
| **CI Actions Status** | Passing | 1 suite | 2026-10-06 | `.github/workflows/` logs in GitHub |
