"""
Unit tests for the validator hard gate (7 conditions).
No LLM, no database. Pure deterministic validation logic.
"""
from backend.validator.hard_gate import (
    validate_analysis,
)


def _base_raw(overrides=None):
    """Minimal valid analysis payload."""
    d = {
        "summary": "The agent handled a billing query from the customer.",
        "reasons": ["billing_dispute"],
        "resolution": "resolved",
        "churn_risk": "low",
        "churn_signals": [],
        "sentiment_trajectory": [{"turn_id": "turn_0001", "sentiment": "neutral"}],
        "false_resolution": False,
        "false_resolution_reason": "",
        "commitments": [],
    }
    if overrides:
        d.update(overrides)
    return d


def _turns():
    return {
        "turn_0001": "The agent greeted the customer.",
        "turn_0002": "The customer explained the billing issue.",
    }


class TestValidConditions:
    def test_valid_payload_passes(self):
        r = validate_analysis(_base_raw(), _turns())
        assert r.passed
        assert r.errors == []

    def test_valid_with_qa_items(self):
        qa = [{"item_id": "greeting", "result": "pass", "explanation": "Agent greeted",
               "quote": "greeted", "turn_id": "turn_0001", "confidence": 0.95,
               "human_review_required": False}]
        r = validate_analysis(_base_raw(), _turns(), qa)
        assert r.passed


class TestCondition1TurnIdExists:
    def test_invalid_turn_id_in_commitment_flagged(self):
        raw = _base_raw({"commitments": [
            {"description": "Send bill", "owner": "agent", "deadline": "", "deadline_flag": "",
             "status": "proposed", "turn_id": "turn_9999", "quote": ""}
        ]})
        r = validate_analysis(raw, _turns())
        assert not r.passed
        assert any(e.code == "unsupported_evidence" for e in r.errors)

    def test_valid_commitment_turn_id_passes(self):
        raw = _base_raw({"resolution": "pending", "commitments": [
            {"description": "Send bill", "owner": "agent", "deadline": "", "deadline_flag": "",
             "status": "proposed", "turn_id": "turn_0001", "quote": ""}  # empty quote OK
        ]})
        r = validate_analysis(raw, _turns())
        assert r.passed

    def test_empty_turn_id_in_commitment_not_flagged(self):
        raw = _base_raw({"resolution": "pending", "commitments": [
            {"description": "Send bill", "owner": "agent", "deadline": "", "deadline_flag": "",
             "status": "proposed", "turn_id": "", "quote": ""}  # empty turn_id is skipped
        ]})
        r = validate_analysis(raw, _turns())
        assert r.passed  # empty turn_id is allowed (not checkable)


class TestCondition2ExactQuote:
    def test_quote_not_in_turn_flagged(self):
        raw = _base_raw({"commitments": [
            {"description": "desc", "owner": "agent", "deadline": "", "deadline_flag": "",
             "status": "proposed", "turn_id": "turn_0001", "quote": "This text is not in the turn"}
        ]})
        r = validate_analysis(raw, _turns())
        assert not r.passed
        assert any(e.field == "commitments[0].quote" for e in r.errors)

    def test_exact_quote_match_passes(self):
        raw = _base_raw({"resolution": "pending", "commitments": [
            {"description": "desc", "owner": "agent", "deadline": "", "deadline_flag": "",
             "status": "proposed", "turn_id": "turn_0001", "quote": "greeted the customer"}
            # turn_0001 is "The agent greeted the customer." — substring matches
        ]})
        r = validate_analysis(raw, _turns())
        assert r.passed

    def test_case_insensitive_quote_match(self):
        raw = _base_raw({"resolution": "pending", "commitments": [
            {"description": "desc", "owner": "agent", "deadline": "", "deadline_flag": "",
             "status": "proposed", "turn_id": "turn_0001", "quote": "GREETED THE CUSTOMER"}
        ]})
        r = validate_analysis(raw, _turns())
        assert r.passed


class TestCondition3LabelTaxonomy:
    def test_invalid_reason_flagged(self):
        raw = _base_raw({"reasons": ["invalid_reason_not_in_taxonomy"]})
        r = validate_analysis(raw, _turns())
        assert not r.passed
        assert any(e.field == "reasons" for e in r.errors)

    def test_valid_reason_passes(self):
        raw = _base_raw({"reasons": ["billing_dispute", "general_inquiry"]})
        r = validate_analysis(raw, _turns())
        assert r.passed

    def test_invalid_resolution_flagged(self):
        raw = _base_raw({"resolution": "magic_resolution"})
        r = validate_analysis(raw, _turns())
        assert not r.passed

    def test_invalid_churn_risk_flagged(self):
        raw = _base_raw({"churn_risk": "extreme"})
        r = validate_analysis(raw, _turns())
        assert not r.passed

    def test_invalid_sentiment_in_trajectory_flagged(self):
        raw = _base_raw({"sentiment_trajectory": [
            {"turn_id": "turn_0001", "sentiment": "happy"}  # not in enum
        ]})
        r = validate_analysis(raw, _turns())
        assert not r.passed


class TestCondition5ResolutionConsistency:
    def test_resolved_with_open_commitment_flagged(self):
        raw = _base_raw({
            "resolution": "resolved",
            "commitments": [{
                "description": "Follow up", "owner": "agent", "deadline": "", "deadline_flag": "",
                "status": "proposed",  # open!
                "turn_id": "turn_0001", "quote": ""
            }]
        })
        r = validate_analysis(raw, _turns())
        assert not r.passed
        assert any(e.code == "inconsistent_state" for e in r.errors)

    def test_partially_resolved_with_open_commitment_passes(self):
        raw = _base_raw({
            "resolution": "partially_resolved",
            "commitments": [{
                "description": "Follow up", "owner": "agent", "deadline": "", "deadline_flag": "",
                "status": "proposed",
                "turn_id": "turn_0001", "quote": ""
            }]
        })
        r = validate_analysis(raw, _turns())
        assert r.passed

    def test_resolved_with_all_commitments_done_passes(self):
        raw = _base_raw({
            "resolution": "resolved",
            "commitments": [{
                "description": "Follow up", "owner": "agent", "deadline": "", "deadline_flag": "",
                "status": "completed",
                "turn_id": "turn_0001",
                "quote": "greeted the customer"  # quote is in turn_0001
            }]
        })
        r = validate_analysis(raw, _turns())
        assert r.passed


class TestCondition7SummaryConsistency:
    def test_summary_with_resolved_but_resolution_unresolved_flagged(self):
        raw = _base_raw({
            "summary": "The agent resolved the customer's query successfully.",
            "resolution": "unresolved",  # contradicts summary
        })
        r = validate_analysis(raw, _turns())
        assert not r.passed
        assert any(e.field == "summary" for e in r.errors)

    def test_summary_without_outcome_words_passes(self):
        raw = _base_raw({
            "summary": "The customer called about a billing issue. The agent took details.",
            "resolution": "unresolved",
        })
        r = validate_analysis(raw, _turns())
        assert r.passed

    def test_summary_resolved_with_resolved_resolution_passes(self):
        raw = _base_raw({
            "summary": "Agent resolved the billing dispute.",
            "resolution": "resolved",
        })
        r = validate_analysis(raw, _turns())
        assert r.passed
