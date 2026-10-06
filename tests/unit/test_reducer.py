"""
Unit tests for the state reducer and windowing utilities.
"""
from backend.domain_model import ChurnRisk, CustomerSentiment, ResolutionStatus
from backend.state.reducer import apply_turn_extraction, initial_state


def _state(conv_id="test-conv"):
    return initial_state(conv_id)


class TestInitialState:
    def test_initial_state_structure(self):
        s = _state()
        assert s["resolution"] == ResolutionStatus.UNKNOWN.value
        assert s["sentiment_current"] == CustomerSentiment.NEUTRAL.value
        assert s["churn_risk"] == ChurnRisk.LOW.value
        assert s["commitments"] == []
        assert s["provisional"] is True

    def test_initial_state_has_conversation_id(self):
        s = _state("abc-123")
        assert s["conversation_id"] == "abc-123"


class TestApplyTurnExtraction:
    def test_resolution_update(self):
        s = _state()
        s2 = apply_turn_extraction(s, {"resolution_update": "resolved", "sentiment": "positive",
                                        "new_commitments": [], "completed_commitments": [], "churn_signal": "none"},
                                    "turn_0001", "Agent resolved the issue.")
        assert s2["resolution"] == "resolved"

    def test_no_change_resolution_preserved(self):
        s = _state()
        s["resolution"] = "partially_resolved"
        s2 = apply_turn_extraction(s, {"resolution_update": "no_change", "sentiment": "neutral",
                                        "new_commitments": [], "completed_commitments": [], "churn_signal": "none"},
                                    "turn_0001", "Some text.")
        assert s2["resolution"] == "partially_resolved"

    def test_sentiment_trajectory_appended(self):
        s = _state()
        s2 = apply_turn_extraction(s, {"resolution_update": "no_change", "sentiment": "frustrated",
                                        "new_commitments": [], "completed_commitments": [], "churn_signal": "none"},
                                    "turn_0001", "I am very frustrated.")
        assert s2["sentiment_current"] == "frustrated"
        assert len(s2["sentiment_trajectory"]) == 1
        assert s2["sentiment_trajectory"][0]["turn_id"] == "turn_0001"

    def test_sentiment_trajectory_cumulates(self):
        s = _state()
        s2 = apply_turn_extraction(s, {"resolution_update": "no_change", "sentiment": "frustrated",
                                        "new_commitments": [], "completed_commitments": [], "churn_signal": "none"},
                                    "turn_0001", "Frustrating.")
        s3 = apply_turn_extraction(s2, {"resolution_update": "no_change", "sentiment": "positive",
                                         "new_commitments": [], "completed_commitments": [], "churn_signal": "none"},
                                     "turn_0002", "Thank you!")
        assert len(s3["sentiment_trajectory"]) == 2
        assert s3["sentiment_current"] == "positive"

    def test_churn_signal_escalation(self):
        s = _state()
        s2 = apply_turn_extraction(s, {"resolution_update": "no_change", "sentiment": "angry",
                                        "new_commitments": [], "completed_commitments": [], "churn_signal": "high"},
                                    "turn_0001", "I want to cancel.")
        assert s2["churn_risk"] == "high"
        assert "high" in s2["churn_signals"]

    def test_new_commitment_added(self):
        s = _state()
        s2 = apply_turn_extraction(s, {
            "resolution_update": "no_change",
            "sentiment": "neutral",
            "churn_signal": "none",
            "new_commitments": [{
                "description": "Send bill copy",
                "owner": "agent",
                "deadline": "2 business days",
                "deadline_flag": "soft",
                "turn_id": "turn_0001",
                "quote": "I will send you a copy"
            }],
            "completed_commitments": [],
        }, "turn_0001", "I will send you a copy of the bill.")
        assert len(s2["commitments"]) == 1
        assert s2["commitments"][0]["description"] == "Send bill copy"
        assert s2["commitments"][0]["provisional"] is True

    def test_commitment_completed(self):
        s = _state()
        # Add a commitment first
        s2 = apply_turn_extraction(s, {
            "resolution_update": "no_change", "sentiment": "neutral", "churn_signal": "none",
            "new_commitments": [{"description": "Send bill", "owner": "agent",
                                  "deadline": "", "deadline_flag": "", "turn_id": "turn_0001", "quote": ""}],
            "completed_commitments": [],
        }, "turn_0001", "I will send the bill.")
        commit_id = s2["commitments"][0]["commitment_id"]

        # Mark as completed
        s3 = apply_turn_extraction(s2, {
            "resolution_update": "no_change", "sentiment": "positive", "churn_signal": "none",
            "new_commitments": [],
            "completed_commitments": [commit_id],
        }, "turn_0002", "Bill sent successfully.")
        assert s3["commitments"][0]["status"] == "completed"
        assert s3["commitments"][0]["completed_at_turn_id"] == "turn_0002"

    def test_state_is_immutable_original_unchanged(self):
        s = _state()
        s["resolution"] = "pending"
        s2 = apply_turn_extraction(s, {"resolution_update": "resolved", "sentiment": "positive",
                                        "new_commitments": [], "completed_commitments": [], "churn_signal": "none"},
                                    "turn_0001", "Resolved.")
        # Original state unchanged
        assert s["resolution"] == "pending"
        assert s2["resolution"] == "resolved"

    def test_as_of_turn_id_updated(self):
        s = _state()
        s2 = apply_turn_extraction(s, {"resolution_update": "no_change", "sentiment": "neutral",
                                        "new_commitments": [], "completed_commitments": [], "churn_signal": "none"},
                                    "turn_0005", "text")
        assert s2["as_of_turn_id"] == "turn_0005"
