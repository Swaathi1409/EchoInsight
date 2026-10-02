"""QA scorer: compute coverage, score, and compliance flags from LLM QA items."""
from __future__ import annotations
import uuid
from backend.domain_model import DEFAULT_COVERAGE_THRESHOLD, DEFAULT_CRITICAL_VIOLATION_SCORE_CAP

ITEM_WEIGHTS = {
    "greeting": 1.0,
    "identity_verification": 2.0,
    "empathy": 1.5,
    "disclosure": 1.5,
    "prohibited_promises": 2.0,
    "closure": 1.0,
}
CRITICAL_ITEMS = {"identity_verification", "prohibited_promises", "disclosure"}


def score(items: list[dict]) -> dict:
    """
    Compute QA result from validated item list.
    Each item: {item_id, result, explanation, turn_id, quote, confidence, human_review_required}
    Returns dict matching QAResultResponse fields.
    """
    applicable, assessed, needs_review_count = 0, 0, 0
    applicable_weight = assessed_weight = 0.0
    passed_weight = 0.0
    critical_violation = False
    scored_items = []

    for item in items:
        item_id = item.get("item_id", "")
        result = item.get("result", "needs_review")
        weight = ITEM_WEIGHTS.get(item_id, 1.0)

        if result == "not_applicable":
            scored_items.append({**item, "weight": weight, "score_contribution": 0.0,
                                  "finding_type": None})
            continue

        applicable += 1
        applicable_weight += weight

        if result == "needs_review":
            needs_review_count += 1
            scored_items.append({**item, "weight": weight, "score_contribution": 0.0,
                                  "finding_type": None})
            continue

        assessed += 1
        assessed_weight += weight

        if result == "pass":
            passed_weight += weight
            scored_items.append({**item, "weight": weight,
                                  "score_contribution": weight, "finding_type": None})
        else:  # fail
            if item_id in CRITICAL_ITEMS:
                critical_violation = True
            finding_type = "confirmed_violation" if item_id == "prohibited_promises" else "potential_concern"
            scored_items.append({**item, "weight": weight, "score_contribution": 0.0,
                                  "finding_type": finding_type})

    coverage = assessed_weight / applicable_weight if applicable_weight > 0 else 0.0

    if applicable == 0:
        score_val, score_label = 0, "not_assessed"
    elif coverage < DEFAULT_COVERAGE_THRESHOLD:
        raw = (passed_weight / assessed_weight * 100) if assessed_weight > 0 else 0.0
        if critical_violation:
            raw = min(raw, DEFAULT_CRITICAL_VIOLATION_SCORE_CAP)
        score_val, score_label = raw, "partial"
    else:
        raw = (passed_weight / assessed_weight * 100) if assessed_weight > 0 else 0.0
        if critical_violation:
            raw = min(raw, DEFAULT_CRITICAL_VIOLATION_SCORE_CAP)
        score_val, score_label = raw, "score"

    return {
        "qa_result_id": str(uuid.uuid4()),
        "score": round(score_val, 1),
        "score_label": score_label,
        "coverage": round(coverage, 3),
        "items_applicable": applicable,
        "items_assessed": assessed,
        "items_needs_review": needs_review_count,
        "critical_violation": critical_violation,
        "items": scored_items,
    }
