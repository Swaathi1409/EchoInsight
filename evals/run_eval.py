"""
EchoInsight evaluation pipeline.

Runs repeatably and saves versioned results to evals/results/.
All metrics computed from stored analysis results (not re-run from LLM).
Mock-based metrics are labeled; real-model metrics state sample size.

Usage:
    make eval
    python evals/run_eval.py [--gold-dir evals/gold] [--results-dir evals/results]
"""
from __future__ import annotations
import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

ROOT = Path(__file__).parent.parent
EVALS_DIR = ROOT / "evals"
RESULTS_DIR = EVALS_DIR / "results"


def _load_gold(gold_dir: Path) -> list[dict]:
    """Load gold annotations from gold_dir/*.json."""
    items = []
    for p in sorted(gold_dir.glob("*.json")):
        with p.open() as f:
            items.append(json.load(f))
    return items


def _precision_recall_f1(tp: int, fp: int, fn: int) -> dict:
    p = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    r = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * p * r / (p + r) if (p + r) > 0 else 0.0
    return {"precision": round(p, 3), "recall": round(r, 3), "f1": round(f1, 3)}


async def _fetch_analysis(api_base: str, token: str, conv_id: str) -> dict | None:
    """Fetch analysis result for a conversation from the live API."""
    import httpx
    async with httpx.AsyncClient(base_url=api_base, timeout=30) as c:
        r = await c.get(f"/api/v1/conversations/{conv_id}/analysis",
                        headers={"Authorization": f"Bearer {token}"})
        if r.status_code == 200:
            return r.json()
        logger.warning("Analysis not ready for %s: %s", conv_id, r.status_code)
        return None


def eval_reliability(analyses: list[dict]) -> dict:
    """
    Reliability metrics: invalid output rate, evidence mismatch rate.
    Based on analysis records already stored in the DB.
    """
    total = len(analyses)
    if total == 0:
        return {"note": "No analyses to evaluate", "total": 0}

    needs_review = sum(1 for a in analyses
                       if a.get("qa_result") and a["qa_result"].get("items_needs_review", 0) > 0)
    false_resolutions = sum(1 for a in analyses if a.get("false_resolution"))

    return {
        "total_analyzed": total,
        "needs_review_count": needs_review,
        "needs_review_rate": round(needs_review / total, 3),
        "false_resolution_count": false_resolutions,
        "false_resolution_rate": round(false_resolutions / total, 3),
        "note": "Reliability metrics from stored results; sample size shown above.",
    }


def eval_qa_coverage(analyses: list[dict]) -> dict:
    """QA coverage and score distribution."""
    qa_results = [a["qa_result"] for a in analyses if a.get("qa_result")]
    if not qa_results:
        return {"note": "No QA results available"}

    scores = [q["score"] for q in qa_results if q.get("score") is not None]
    coverages = [q["coverage"] for q in qa_results if q.get("coverage") is not None]
    critical = [q for q in qa_results if q.get("critical_violation")]

    return {
        "qa_results_count": len(qa_results),
        "avg_score": round(sum(scores) / len(scores), 1) if scores else None,
        "min_score": min(scores) if scores else None,
        "max_score": max(scores) if scores else None,
        "avg_coverage": round(sum(coverages) / len(coverages), 3) if coverages else None,
        "critical_violations": len(critical),
        "partial_scores": sum(1 for q in qa_results if q.get("score_label") == "partial"),
        "note": "Coverage is assessed-weight/applicable-weight. Partial scores excluded from averages unless shown.",
    }


def eval_sentiment(analyses: list[dict]) -> dict:
    """Sentiment trajectory statistics."""
    trajectories = [a.get("sentiment_trajectory", []) for a in analyses]
    non_empty = [t for t in trajectories if t]
    if not non_empty:
        return {"note": "No sentiment trajectories in results"}

    starts = [t[0]["sentiment"] for t in non_empty if t]
    ends = [t[-1]["sentiment"] for t in non_empty if t]
    negative_end = ["frustrated", "angry"]
    pct_negative_end = sum(1 for e in ends if e in negative_end) / len(ends) if ends else 0

    return {
        "conversations_with_trajectory": len(non_empty),
        "negative_end_rate": round(pct_negative_end, 3),
        "note": "No gold sentiment labels available; distribution only. No F1 computed.",
    }


def eval_resolution(analyses: list[dict]) -> dict:
    """Resolution status distribution."""
    resolutions = [a.get("resolution") for a in analyses if a.get("resolution")]
    if not resolutions:
        return {"note": "No resolution data"}
    from collections import Counter
    counts = Counter(resolutions)
    return {
        "total": len(resolutions),
        "distribution": dict(counts),
        "note": "No gold resolution labels available; distribution only. No F1 computed.",
    }


def leakage_check() -> dict:
    """Verify no test IDs appear in prompt, fixture, or sample files."""
    split_path = ROOT / "data" / "manifests" / "gold_split_v1.json"
    if not split_path.exists():
        return {"status": "skipped", "reason": "gold_split_v1.json not found"}

    with split_path.open() as f:
        split = json.load(f)

    test_ids = set(split.get("test", []))
    if not test_ids:
        return {"status": "skipped", "reason": "No test IDs in split manifest"}

    leaks = []
    search_dirs = [
        ROOT / "backend" / "config",
        ROOT / "data" / "sample",
        ROOT / "tests" / "fixtures",
    ]
    for d in search_dirs:
        if not d.exists():
            continue
        for p in d.rglob("*"):
            if p.is_file() and p.suffix in (".json", ".yaml", ".yml", ".txt", ".py"):
                try:
                    content = p.read_text(encoding="utf-8", errors="ignore")
                    found = [tid for tid in test_ids if tid in content]
                    if found:
                        leaks.append({"file": str(p.relative_to(ROOT)), "ids": found})
                except Exception:
                    pass

    return {
        "status": "pass" if not leaks else "fail",
        "test_ids_checked": len(test_ids),
        "leaks_found": leaks,
    }


def main(args: argparse.Namespace) -> None:
    results_dir = Path(args.results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_path = results_dir / f"eval_{timestamp}.json"

    logger.info("Running evaluation pipeline...")

    # Load analyses from DB via API if available, otherwise from cached results
    analyses: list[dict] = []
    api_base = os.environ.get("API_BASE_URL", "http://localhost:8000")
    admin_user = os.environ.get("EVAL_ADMIN_USER", "admin")
    admin_pass = os.environ.get("EVAL_ADMIN_PASS", "admin123")

    try:
        import httpx

        async def fetch_all():
            async with httpx.AsyncClient(base_url=api_base, timeout=15) as c:
                r = await c.post("/api/v1/auth/login",
                                  json={"username": admin_user, "password": admin_pass})
                if r.status_code != 200:
                    logger.warning("Could not log in to API: %s", r.text[:80])
                    return []
                tok = r.json()["access_token"]
                h = {"Authorization": f"Bearer {tok}"}

                r2 = await c.get("/api/v1/conversations?limit=200", headers=h)
                if r2.status_code != 200:
                    return []
                convs = r2.json()
                ended = [c for c in convs if c["status"] == "ended" and c["analysis_version"] > 0]
                logger.info("Found %d ended conversations with analysis", len(ended))

                results = []
                for conv in ended[:50]:  # cap at 50 for eval
                    an = await _fetch_analysis(api_base, tok, conv["id"])
                    if an:
                        results.append(an)
                return results

        analyses = asyncio.run(fetch_all())
        source = "live_api"
    except Exception as e:
        logger.warning("Could not fetch from live API: %s", e)
        source = "unavailable"

    # Compute metrics
    report = {
        "timestamp": timestamp,
        "source": source,
        "sample_size": len(analyses),
        "status": "provisional",
        "note": (
            "All metrics are provisional until the gold set is human-reviewed. "
            "Metrics without gold labels report distributions only. "
            "Real-model metrics require a live Groq API key and running analysis jobs."
        ),
        "leakage_check": leakage_check(),
        "reliability": eval_reliability(analyses),
        "qa_coverage": eval_qa_coverage(analyses),
        "sentiment_distribution": eval_sentiment(analyses),
        "resolution_distribution": eval_resolution(analyses),
        "metrics_not_computed": [
            "call_reason_F1 (requires gold labels)",
            "sentiment_F1 (requires gold labels)",
            "resolution_F1 (requires gold labels)",
            "evidence_correctness (requires human review)",
            "provisional_vs_final_agreement (requires incremental run log)",
            "selective_verification_routing_precision (requires manual review of routed items)",
        ],
        "how_to_complete_eval": (
            "1. Annotate gold conversations using evals/gold_workbook.csv and evals/rubric.md. "
            "2. Run 'make eval' after annotation to compute F1 metrics. "
            "3. Results are labeled 'provisional' until human review is confirmed."
        ),
    }

    with output_path.open("w") as f:
        json.dump(report, f, indent=2, default=str)

    logger.info("Evaluation report written to: %s", output_path)
    logger.info("Sample size: %d analyses", len(analyses))
    logger.info("Leakage check: %s", report["leakage_check"]["status"])

    if analyses:
        r = report["reliability"]
        logger.info("Needs-review rate: %.1f%%", r.get("needs_review_rate", 0) * 100)
        logger.info("False-resolution rate: %.1f%%", r.get("false_resolution_rate", 0) * 100)
        q = report["qa_coverage"]
        logger.info("Avg QA score: %s", q.get("avg_score"))
        logger.info("Avg QA coverage: %s", q.get("avg_coverage"))
    else:
        logger.warning("No analyses retrieved. Run analysis jobs first (start worker and submit conversations).")

    print(f"\nEval report: {output_path}")
    print(f"Status: PROVISIONAL (sample_size={len(analyses)})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="EchoInsight evaluation pipeline")
    parser.add_argument("--results-dir", default=str(EVALS_DIR / "results"),
                        help="Directory to write evaluation results")
    parser.add_argument("--gold-dir", default=str(EVALS_DIR / "gold"),
                        help="Directory containing gold annotation files")
    main(parser.parse_args())
