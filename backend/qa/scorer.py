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


def score(items: list[dict], db_items: list = None, settings: dict = None) -> dict:
    """
    Compute QA result from validated item list using dynamic settings.
    Each item: {item_id, result, explanation, turn_id, quote, confidence, human_review_required}
    """
    applicable, assessed, needs_review_count = 0, 0, 0
    applicable_weight = assessed_weight = 0.0
    passed_weight = 0.0
    critical_violation = False
    scored_items = []

    db_items = db_items or []
    settings = settings or {}
    scoring_settings = settings.get("scoring", {})

    # Map for easy lookup
    db_items_map = {}
    for di in db_items:
        key = getattr(di, 'item_key', None) or (di.get('item_key') if isinstance(di, dict) else '')
        if not key and isinstance(di, dict) and 'id' in di:
            key = di['id']
        db_items_map[key] = di

    for item in items:
        item_id = item.get("item_id", "")
        result = item.get("result", "needs_review")

        db_item = db_items_map.get(item_id)
        if db_item:
            weight = getattr(db_item, 'weight', 1.0) if not isinstance(db_item, dict) else db_item.get('weight', 1.0)
            is_critical = getattr(db_item, 'critical', False) if not isinstance(db_item, dict) else db_item.get('critical', False)
        else:
            weight = ITEM_WEIGHTS.get(item_id, 1.0)
            is_critical = item_id in CRITICAL_ITEMS

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
            if is_critical:
                critical_violation = True
            finding_type = "confirmed_violation" if item_id == "prohibited_promises" else "potential_concern"
            scored_items.append({**item, "weight": weight, "score_contribution": 0.0,
                                  "finding_type": finding_type})

    coverage = assessed_weight / applicable_weight if applicable_weight > 0 else 0.0
    cov_threshold = scoring_settings.get("coverage_threshold", DEFAULT_COVERAGE_THRESHOLD)
    crit_cap = scoring_settings.get("critical_violation_score_cap", DEFAULT_CRITICAL_VIOLATION_SCORE_CAP)

    if applicable == 0:
        score_val, score_label = None, "not_assessed"
    elif coverage < cov_threshold:
        raw = (passed_weight / assessed_weight * 100) if assessed_weight > 0 else 0.0
        penalty = scoring_settings.get("needs_review_coverage_penalty", 0.0)
        raw = max(0.0, raw - (raw * penalty))
        if critical_violation:
            raw = min(raw, crit_cap)
        score_val, score_label = round(raw, 1), scoring_settings.get("partial_score_label", "partial")
    else:
        raw = (passed_weight / assessed_weight * 100) if assessed_weight > 0 else 0.0
        if critical_violation:
            raw = min(raw, crit_cap)
        score_val, score_label = round(raw, 1), "score"

    return {
        "qa_result_id": str(uuid.uuid4()),
        "score": score_val,
        "score_label": score_label,
        "coverage": round(coverage, 3),
        "items_applicable": applicable,
        "items_assessed": assessed,
        "items_needs_review": needs_review_count,
        "critical_violation": critical_violation,
        "items": scored_items,
    }
