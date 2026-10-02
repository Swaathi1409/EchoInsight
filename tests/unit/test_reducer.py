"""Unit tests for state reducer."""
from backend.state.reducer import apply_turn_extraction, initial_state
from backend.domain_model import ChurnRisk, CommitmentStatus, ResolutionStatus


def test_initial_state_shape():
    s = initial_state("conv-1")
    assert s["conversation_id"] == "conv-1"
    assert s["resolution"] == ResolutionStatus.UNKNOWN.value
    assert s["churn_risk"] == ChurnRisk.LOW.value
    assert s["commitments"] == []
    assert s["provisional"] is True


def test_resolution_updated():
    state = initial_state("conv-1")
    extraction = {"resolution_update": "resolved", "sentiment": "positive",
                  "new_commitments": [], "completed_commitments": [], "churn_signal": "none"}
    new = apply_turn_extraction(state, extraction, "turn_0001", "text")
    assert new["resolution"] == "resolved"


def test_no_change_keeps_resolution():
    state = initial_state("conv-1")
    state["resolution"] = "resolved"
    extraction = {"resolution_update": "no_change", "sentiment": "neutral",
                  "new_commitments": [], "completed_commitments": [], "churn_signal": "none"}
    new = apply_turn_extraction(state, extraction, "turn_0002", "text")
    assert new["resolution"] == "resolved"


def test_sentiment_trajectory_grows():
    state = initial_state("conv-1")
    for i, sent in enumerate(["positive", "frustrated", "angry"], 1):
        extraction = {"resolution_update": "no_change", "sentiment": sent,
                      "new_commitments": [], "completed_commitments": [], "churn_signal": "none"}
        state = apply_turn_extraction(state, extraction, f"turn_{i:04d}", "text")
    assert len(state["sentiment_trajectory"]) == 3
    assert state["sentiment_current"] == "angry"


def test_commitment_added():
    state = initial_state("conv-1")
    extraction = {
        "resolution_update": "no_change", "sentiment": "neutral", "churn_signal": "none",
        "new_commitments": [{"description": "Send replacement SIM", "owner": "agent",
                             "deadline": "2 business days", "deadline_flag": "explicit",
                             "turn_id": "turn_0001", "quote": "send a replacement SIM"}],
        "completed_commitments": [],
    }
    new = apply_turn_extraction(state, extraction, "turn_0001", "send a replacement SIM")
    assert len(new["commitments"]) == 1
    c = new["commitments"][0]
    assert c["status"] == CommitmentStatus.PROPOSED.value
    assert c["description"] == "Send replacement SIM"


def test_churn_signal_escalates_risk():
    state = initial_state("conv-1")
    extraction = {"resolution_update": "no_change", "sentiment": "angry",
                  "new_commitments": [], "completed_commitments": [], "churn_signal": "high"}
    new = apply_turn_extraction(state, extraction, "turn_0001", "text")
    assert new["churn_risk"] == ChurnRisk.HIGH.value


def test_reducer_immutable():
    """apply_turn_extraction must not mutate the input state dict."""
    state = initial_state("conv-1")
    original_id = id(state["commitments"])
    extraction = {"resolution_update": "no_change", "sentiment": "neutral",
                  "new_commitments": [], "completed_commitments": [], "churn_signal": "none"}
    apply_turn_extraction(state, extraction, "turn_0001", "text")
    assert id(state["commitments"]) == original_id
