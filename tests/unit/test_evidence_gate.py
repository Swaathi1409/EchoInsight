"""Unit tests for evidence gate — pure function, no DB, no LLM."""
from backend.validator.evidence_gate import check_quote, gate_commitments, gate_qa_items

TURN_TEXT = "The customer wants to cancel their plan due to poor coverage in the downtown area."


def test_exact_quote_passes():
    assert check_quote("cancel their plan", TURN_TEXT)


def test_case_insensitive_match():
    assert check_quote("CANCEL THEIR PLAN", TURN_TEXT)


def test_extra_whitespace_normalized():
    assert check_quote("cancel  their   plan", TURN_TEXT)


def test_wrong_quote_fails():
    assert not check_quote("customer loves the service", TURN_TEXT)


def test_empty_quote_passes():
    assert check_quote("", TURN_TEXT)


def test_very_short_quote_passes():
    assert check_quote("ok", TURN_TEXT)


def test_gate_commitments_pass():
    turns = {"turn_0001": TURN_TEXT}
    commitments = [{"turn_id": "turn_0001", "quote": "cancel their plan",
                    "description": "Cancel plan", "owner": "agent", "deadline": "today",
                    "deadline_flag": "explicit", "status": "proposed"}]
    result = gate_commitments(commitments, turns)
    assert result[0]["needs_review"] is False


def test_gate_commitments_fail_flags_needs_review():
    turns = {"turn_0001": TURN_TEXT}
    commitments = [{"turn_id": "turn_0001", "quote": "customer loves the service",
                    "description": "Something", "owner": "agent", "deadline": "tomorrow",
                    "deadline_flag": "explicit", "status": "proposed"}]
    result = gate_commitments(commitments, turns)
    assert result[0]["needs_review"] is True
    assert result[0]["evidence_flag"] == "quote_mismatch"


def test_gate_qa_items_pass():
    turns = {"turn_0001": TURN_TEXT}
    items = [{"item_id": "greeting", "result": "pass", "explanation": "ok",
              "turn_id": "turn_0001", "quote": "cancel their plan",
              "confidence": 0.9, "human_review_required": False}]
    result = gate_qa_items(items, turns, TURN_TEXT)
    assert result[0]["result"] == "pass"


def test_gate_qa_items_bad_quote_becomes_needs_review():
    turns = {"turn_0001": TURN_TEXT}
    items = [{"item_id": "greeting", "result": "pass", "explanation": "ok",
              "turn_id": "turn_0001", "quote": "completely fabricated statement",
              "confidence": 0.9, "human_review_required": False}]
    result = gate_qa_items(items, turns, TURN_TEXT)
    assert result[0]["result"] == "needs_review"
    assert result[0]["human_review_required"] is True


def test_gate_qa_no_turn_id_falls_back_to_full_text():
    items = [{"item_id": "greeting", "result": "pass", "explanation": "ok",
              "turn_id": "", "quote": "cancel their plan",
              "confidence": 0.9, "human_review_required": False}]
    result = gate_qa_items(items, {}, TURN_TEXT)
    assert result[0]["result"] == "pass"
