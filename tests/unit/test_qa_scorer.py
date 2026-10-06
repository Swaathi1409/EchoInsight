"""Unit tests for QA scorer — pure function, no DB, no LLM."""
from backend.qa.scorer import CRITICAL_ITEMS, ITEM_WEIGHTS, score


def _item(item_id, result, confidence=0.9, quote="test quote", turn_id="turn_0001", hr=False):
    return {"item_id": item_id, "result": result, "explanation": "test",
            "turn_id": turn_id, "quote": quote, "confidence": confidence,
            "human_review_required": hr}


def test_all_pass():
    items = [_item(k, "pass") for k in ITEM_WEIGHTS]
    r = score(items)
    assert r["score"] == 100.0
    assert r["coverage"] == 1.0
    assert not r["critical_violation"]
    assert r["items_assessed"] == len(ITEM_WEIGHTS)


def test_all_fail():
    items = [_item(k, "fail") for k in ITEM_WEIGHTS]
    r = score(items)
    assert r["score"] == 0.0 or r["score"] is None
    assert r["critical_violation"]  # critical items in there


def test_critical_violation_caps_score():
    items = [_item(k, "pass") for k in ITEM_WEIGHTS if k not in CRITICAL_ITEMS]
    items += [_item(k, "fail") for k in CRITICAL_ITEMS]
    r = score(items)
    assert r["critical_violation"]
    from backend.domain_model import DEFAULT_CRITICAL_VIOLATION_SCORE_CAP
    if r["score"] is not None:
        assert r["score"] <= DEFAULT_CRITICAL_VIOLATION_SCORE_CAP


def test_not_applicable_excluded_from_score():
    items = [_item("greeting", "pass"), _item("identity_verification", "not_applicable"),
             _item("empathy", "pass"), _item("disclosure", "not_applicable"),
             _item("prohibited_promises", "pass"), _item("closure", "pass")]
    r = score(items)
    assert r["items_applicable"] == 4  # 2 N/A excluded
    assert r["score"] is not None


def test_needs_review_reduces_coverage():
    items = [_item(k, "needs_review") for k in ITEM_WEIGHTS]
    r = score(items)
    assert r["coverage"] == 0.0
    assert r["score_label"] == "partial"
    assert r["items_needs_review"] == len(ITEM_WEIGHTS)


def test_partial_coverage_label():
    items = [_item("greeting", "pass"), _item("identity_verification", "needs_review"),
             _item("empathy", "needs_review"), _item("disclosure", "needs_review"),
             _item("prohibited_promises", "needs_review"), _item("closure", "needs_review")]
    r = score(items)
    assert r["score_label"] == "partial"


def test_empty_items():
    r = score([])
    assert r["score"] is None  # None when no items applicable
    assert r["score_label"] == "not_assessed"
    assert r["coverage"] == 0.0


def test_finding_type_assigned_on_violation():
    items = [_item("prohibited_promises", "fail")]
    r = score(items)
    scored = {i["item_id"]: i for i in r["items"]}
    assert scored["prohibited_promises"]["finding_type"] == "confirmed_violation"


def test_qa_result_has_required_fields():
    items = [_item("greeting", "pass")]
    r = score(items)
    for field in ["qa_result_id", "score", "coverage", "items_applicable",
                  "items_assessed", "items_needs_review", "critical_violation", "items"]:
        assert field in r, f"Missing field: {field}"
