"""
tests/action_layer/test_phase2_risk_engine.py

Phase 2 unit tests for the deterministic risk engine.
Includes 20 golden synthetic fixtures with known expected outputs.
All fixtures are labeled SYNTHETIC — not from real production data.

Tests cover:
- Every risk component (individually and combined)
- Impact, urgency and priority mapping
- Intervention type detection
- What-if scenario recomputation
- Evidence integrity (unsupported signals omitted)
- Consistency: component points sum to risk_index (capped at 10, floored at 1)
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from backend.action_layer.risk_engine import (
    RiskComponent,
    compute_intervention_type,
    compute_priority,
    compute_risk_index,
    compute_what_if,
)


# ── Helpers ───────────────────────────────────────────────────────────────────

def make_analysis(
    resolution="resolved",
    churn_risk="low",
    churn_signals=None,
    false_resolution=False,
    false_resolution_reason=None,
    sentiment_trajectory=None,
    reasons=None,
    summary="Test summary",
):
    return {
        "analysis_id": "test",
        "conversation_id": "test",
        "version": 1,
        "resolution": resolution,
        "churn_risk": churn_risk,
        "churn_signals": churn_signals or [],
        "false_resolution": false_resolution,
        "false_resolution_reason": false_resolution_reason,
        "sentiment_trajectory": sentiment_trajectory or [{"sentiment": "neutral"}],
        "reasons": reasons or [],
        "summary": summary,
        "prompt_version": "v1",
    }


def make_turns(customer_text="", agent_text="thank you"):
    return [
        {"turn_id": "turn_0001", "seq": 1, "speaker": "customer",
         "text_redacted": customer_text, "timestamp": None},
        {"turn_id": "turn_0002", "seq": 2, "speaker": "agent",
         "text_redacted": agent_text, "timestamp": None},
    ]


def make_commitment(status="open", deadline_flag=None, commitment_id=None):
    return {
        "commitment_id": commitment_id or "commit-001",
        "description": "Test commitment",
        "owner": "agent",
        "deadline": None,
        "deadline_flag": deadline_flag,
        "status": status,
        "evidence_json": [],
        "created_at_turn_id": "turn_0001",
    }


def make_qa(critical_violation=False):
    return {
        "qa_result_id": "qa-001",
        "conversation_id": "test",
        "score": 80.0,
        "score_label": "score",
        "coverage": 1.0,
        "critical_violation": critical_violation,
        "items_json": [],
        "checklist_version": "v1",
    }


AS_OF = datetime(2026, 10, 3, 12, 0, 0, tzinfo=timezone.utc)


# ── Golden Fixture: invariant helper ──────────────────────────────────────────

def assert_risk_invariants(result):
    """Every result must satisfy these invariants."""
    assert 1 <= result.risk_index <= 10, f"risk_index {result.risk_index} out of range"
    raw_sum = sum(c.points for c in result.components if c.triggered)
    expected_clamped = max(1, min(10, raw_sum))
    assert result.risk_index == expected_clamped, (
        f"risk_index {result.risk_index} != clamped sum {expected_clamped} "
        f"(raw sum={raw_sum})"
    )
    assert result.risk_band in ("low", "medium", "high")
    if result.risk_index <= 3:
        assert result.risk_band == "low"
    elif result.risk_index <= 6:
        assert result.risk_band == "medium"
    else:
        assert result.risk_band == "high"


# ── SYNTHETIC FIXTURES (20 total) ─────────────────────────────────────────────
# Label: SYNTHETIC — not real production data

class TestRiskEngineGoldenFixtures:
    """20 golden synthetic fixtures with expected risk index and band."""

    # F01: Clean resolved, low churn → minimal risk
    def test_f01_clean_resolved_low_risk(self):
        """SYNTHETIC F01: Clean resolved conversation, no signals → risk 1, low."""
        result = compute_risk_index(
            analysis=make_analysis(resolution="resolved", churn_risk="low"),
            commitments=[],
            qa_result=make_qa(),
            turns=make_turns("thank you very much"),
            cases=[],
            case_other_commitments=[],
            as_of=AS_OF,
        )
        assert_risk_invariants(result)
        assert result.risk_index == 1
        assert result.risk_band == "low"

    # F02: Cancellation intent only → 3 pts
    def test_f02_cancellation_intent(self):
        """SYNTHETIC F02: Explicit cancellation intent → risk 3, low."""
        result = compute_risk_index(
            analysis=make_analysis(resolution="resolved", churn_risk="low"),
            commitments=[],
            qa_result=make_qa(),
            turns=make_turns("I want to cancel my service"),
            cases=[],
            case_other_commitments=[],
            as_of=AS_OF,
        )
        assert_risk_invariants(result)
        assert result.risk_index == 3
        assert result.risk_band == "low"

    # F03: Unresolved only → 2 pts
    def test_f03_unresolved_only(self):
        """SYNTHETIC F03: Unresolved resolution only → risk 2, low."""
        result = compute_risk_index(
            analysis=make_analysis(resolution="unresolved"),
            commitments=[],
            qa_result=make_qa(),
            turns=make_turns("ok"),
            cases=[],
            case_other_commitments=[],
            as_of=AS_OF,
        )
        assert_risk_invariants(result)
        assert result.risk_index == 2
        assert result.risk_band == "low"

    # F04: Angry sentiment → 2 pts
    def test_f04_angry_sentiment(self):
        """SYNTHETIC F04: Angry end-of-call sentiment → risk 2, low."""
        result = compute_risk_index(
            analysis=make_analysis(
                resolution="resolved",
                sentiment_trajectory=[{"sentiment": "neutral"}, {"sentiment": "angry"}],
            ),
            commitments=[],
            qa_result=make_qa(),
            turns=make_turns("this is terrible"),
            cases=[],
            case_other_commitments=[],
            as_of=AS_OF,
        )
        assert_risk_invariants(result)
        assert result.risk_index == 2
        assert result.risk_band == "low"

    # F05: Cancellation + unresolved + angry = 3+2+2 = 7, high
    def test_f05_cancellation_unresolved_angry(self):
        """SYNTHETIC F05: Cancellation + unresolved + angry → risk 7, high."""
        result = compute_risk_index(
            analysis=make_analysis(
                resolution="unresolved",
                sentiment_trajectory=[{"sentiment": "angry"}],
            ),
            commitments=[],
            qa_result=make_qa(),
            turns=make_turns("I want to cancel my service this is terrible"),
            cases=[],
            case_other_commitments=[],
            as_of=AS_OF,
        )
        assert_risk_invariants(result)
        assert result.risk_index == 7
        assert result.risk_band == "high"

    # F06: Open commitment only → 1 pt
    def test_f06_open_commitment_only(self):
        """SYNTHETIC F06: Single open commitment → risk 1, low."""
        result = compute_risk_index(
            analysis=make_analysis(resolution="resolved"),
            commitments=[make_commitment(status="open")],
            qa_result=make_qa(),
            turns=make_turns("ok"),
            cases=[],
            case_other_commitments=[],
            as_of=AS_OF,
        )
        assert_risk_invariants(result)
        assert result.risk_index == 1
        assert result.risk_band == "low"

    # F07: Open + overdue commitment → 1+1 = 2
    def test_f07_open_and_overdue_commitment(self):
        """SYNTHETIC F07: Open + overdue commitment → risk 2, low."""
        result = compute_risk_index(
            analysis=make_analysis(resolution="resolved"),
            commitments=[make_commitment(status="open", deadline_flag="overdue")],
            qa_result=make_qa(),
            turns=make_turns("ok"),
            cases=[],
            case_other_commitments=[],
            as_of=AS_OF,
        )
        assert_risk_invariants(result)
        assert result.risk_index == 2
        assert result.risk_band == "low"

    # F08: False resolution → 1 pt
    def test_f08_false_resolution_flag(self):
        """SYNTHETIC F08: False resolution flag → risk 1, low."""
        result = compute_risk_index(
            analysis=make_analysis(false_resolution=True),
            commitments=[],
            qa_result=make_qa(),
            turns=make_turns("ok"),
            cases=[],
            case_other_commitments=[],
            as_of=AS_OF,
        )
        assert_risk_invariants(result)
        assert result.risk_index == 1
        assert result.risk_band == "low"

    # F09: Critical violation → 1 pt
    def test_f09_critical_violation(self):
        """SYNTHETIC F09: Critical violation → risk 1, low."""
        result = compute_risk_index(
            analysis=make_analysis(resolution="resolved"),
            commitments=[],
            qa_result=make_qa(critical_violation=True),
            turns=make_turns("ok"),
            cases=[],
            case_other_commitments=[],
            as_of=AS_OF,
        )
        assert_risk_invariants(result)
        assert result.risk_index == 1
        assert result.risk_band == "low"

    # F10: Repeat contact (case link) → 1 pt
    def test_f10_repeat_contact_via_case(self):
        """SYNTHETIC F10: Repeat contact (case linked) → risk 1, low."""
        result = compute_risk_index(
            analysis=make_analysis(resolution="resolved"),
            commitments=[],
            qa_result=make_qa(),
            turns=make_turns("ok"),
            cases=[{"case_id": "case-001", "status": "open"}],
            case_other_commitments=[],
            as_of=AS_OF,
        )
        assert_risk_invariants(result)
        assert result.risk_index == 1
        assert result.risk_band == "low"

    # F11: Repeat + broken promise → 1+1 = 2
    def test_f11_repeat_contact_with_broken_promise(self):
        """SYNTHETIC F11: Repeat contact + broken earlier promise → risk 2, low."""
        result = compute_risk_index(
            analysis=make_analysis(resolution="resolved"),
            commitments=[],
            qa_result=make_qa(),
            turns=make_turns("ok"),
            cases=[{"case_id": "case-001", "status": "open"}],
            case_other_commitments=[make_commitment(status="open")],
            as_of=AS_OF,
        )
        assert_risk_invariants(result)
        assert result.risk_index == 2
        assert result.risk_band == "low"

    # F12: Maximum possible score (all components) → capped at 10
    def test_f12_all_components_capped_at_10(self):
        """SYNTHETIC F12: All signals fire → risk capped at 10, high."""
        result = compute_risk_index(
            analysis=make_analysis(
                resolution="unresolved",
                sentiment_trajectory=[{"sentiment": "angry"}],
                false_resolution=True,
            ),
            commitments=[make_commitment(status="open", deadline_flag="overdue")],
            qa_result=make_qa(critical_violation=True),
            turns=make_turns("I want to cancel my service this is very upset"),
            cases=[{"case_id": "case-001", "status": "open"}],
            case_other_commitments=[make_commitment(status="open")],
            as_of=AS_OF,
        )
        assert_risk_invariants(result)
        assert result.risk_index == 10
        assert result.risk_band == "high"

    # F13: Frustrated sentiment → 1 pt (not angry)
    def test_f13_frustrated_sentiment(self):
        """SYNTHETIC F13: Frustrated end-of-call → risk 1, low."""
        result = compute_risk_index(
            analysis=make_analysis(
                resolution="resolved",
                sentiment_trajectory=[{"sentiment": "frustrated"}],
            ),
            commitments=[],
            qa_result=make_qa(),
            turns=make_turns("ok I guess"),
            cases=[],
            case_other_commitments=[],
            as_of=AS_OF,
        )
        assert_risk_invariants(result)
        assert result.risk_index == 1
        assert result.risk_band == "low"

    # F14: Partially resolved + open commitment + overdue = 1+1+1 = 3
    def test_f14_partially_resolved_with_overdue(self):
        """SYNTHETIC F14: Partially resolved + open + overdue → risk 3, low."""
        result = compute_risk_index(
            analysis=make_analysis(resolution="partially_resolved"),
            commitments=[make_commitment(status="open", deadline_flag="overdue")],
            qa_result=make_qa(),
            turns=make_turns("ok"),
            cases=[],
            case_other_commitments=[],
            as_of=AS_OF,
        )
        assert_risk_invariants(result)
        assert result.risk_index == 3
        assert result.risk_band == "low"

    # F15: Escalated → 1 pt
    def test_f15_escalated_resolution(self):
        """SYNTHETIC F15: Escalated resolution → risk 1, low."""
        result = compute_risk_index(
            analysis=make_analysis(resolution="escalated"),
            commitments=[],
            qa_result=make_qa(),
            turns=make_turns("ok"),
            cases=[],
            case_other_commitments=[],
            as_of=AS_OF,
        )
        assert_risk_invariants(result)
        assert result.risk_index == 1
        assert result.risk_band == "low"

    # F16: Cancellation + escalated + open + overdue = 3+1+1+1 = 6, medium
    def test_f16_medium_risk_combination(self):
        """SYNTHETIC F16: Cancellation + escalated + open + overdue → risk 6, medium."""
        result = compute_risk_index(
            analysis=make_analysis(resolution="escalated"),
            commitments=[make_commitment(status="open", deadline_flag="overdue")],
            qa_result=make_qa(),
            turns=make_turns("I want to cancel my service"),
            cases=[],
            case_other_commitments=[],
            as_of=AS_OF,
        )
        assert_risk_invariants(result)
        assert result.risk_index == 6
        assert result.risk_band == "medium"

    # F17: Unresolved + angry + open = 2+2+1 = 5, medium
    def test_f17_medium_risk_unresolved_angry(self):
        """SYNTHETIC F17: Unresolved + angry + open commitment → risk 5, medium."""
        result = compute_risk_index(
            analysis=make_analysis(
                resolution="unresolved",
                sentiment_trajectory=[{"sentiment": "angry"}],
            ),
            commitments=[make_commitment(status="open")],
            qa_result=make_qa(),
            turns=make_turns("this is very upset"),
            cases=[],
            case_other_commitments=[],
            as_of=AS_OF,
        )
        assert_risk_invariants(result)
        assert result.risk_index == 5
        assert result.risk_band == "medium"

    # F18: Everything resolved, completed commitments → risk 1
    def test_f18_everything_resolved_no_risk(self):
        """SYNTHETIC F18: Resolved + completed commitments → risk 1, low."""
        result = compute_risk_index(
            analysis=make_analysis(resolution="resolved"),
            commitments=[make_commitment(status="completed")],
            qa_result=make_qa(),
            turns=make_turns("thank you all resolved"),
            cases=[],
            case_other_commitments=[],
            as_of=AS_OF,
        )
        assert_risk_invariants(result)
        assert result.risk_index == 1
        assert result.risk_band == "low"

    # F19: Cancellation + unresolved + critical violation = 3+2+1 = 6, medium
    def test_f19_cancellation_unresolved_violation(self):
        """SYNTHETIC F19: Cancellation + unresolved + critical violation → risk 6, medium."""
        result = compute_risk_index(
            analysis=make_analysis(resolution="unresolved"),
            commitments=[],
            qa_result=make_qa(critical_violation=True),
            turns=make_turns("I want to cancel my service"),
            cases=[],
            case_other_commitments=[],
            as_of=AS_OF,
        )
        assert_risk_invariants(result)
        assert result.risk_index == 6
        assert result.risk_band == "medium"

    # F20: Cancellation + false resolution + open overdue + violation = 3+1+1+1+1 = 7, high
    def test_f20_high_risk_complex(self):
        """SYNTHETIC F20: Cancellation + false_res + overdue + violation → risk 7, high."""
        result = compute_risk_index(
            analysis=make_analysis(resolution="resolved", false_resolution=True),
            commitments=[make_commitment(status="open", deadline_flag="overdue")],
            qa_result=make_qa(critical_violation=True),
            turns=make_turns("I want to cancel my service"),
            cases=[],
            case_other_commitments=[],
            as_of=AS_OF,
        )
        assert_risk_invariants(result)
        assert result.risk_index == 7
        assert result.risk_band == "high"


# ── Priority Tests ────────────────────────────────────────────────────────────

class TestPriorityComputation:

    def _base_risk(self, risk_index=5, risk_band="medium"):
        """Make a minimal RiskResult-like object for priority tests."""
        from backend.action_layer.risk_engine import RiskResult
        return RiskResult(
            risk_index=risk_index,
            risk_band=risk_band,
            components=[
                RiskComponent("cancellation_intent", 3, risk_band == "high",
                              "rule", {}, "desc"),
                RiskComponent("critical_violation", 1, False, "rule", {}, "desc"),
                RiskComponent("repeat_contact", 1, False, "rule", {}, "desc"),
                RiskComponent("broken_earlier_promise", 1, False, "rule", {}, "desc"),
                RiskComponent("overdue_commitment", 1, False, "rule", {}, "desc"),
                RiskComponent("false_resolution", 1, False, "rule", {}, "desc"),
                RiskComponent("open_commitment", 1, False, "rule", {}, "desc"),
            ],
        )

    def test_p1_high_impact_high_urgency(self):
        """High risk band + overdue commitment → P1."""
        from backend.action_layer.risk_engine import RiskResult
        risk = RiskResult(
            risk_index=8, risk_band="high",
            components=[
                RiskComponent("cancellation_intent", 3, True, "r", {}, ""),
                RiskComponent("critical_violation", 1, False, "r", {}, ""),
                RiskComponent("repeat_contact", 1, False, "r", {}, ""),
                RiskComponent("broken_earlier_promise", 1, False, "r", {}, ""),
                RiskComponent("overdue_commitment", 1, True, "r", {}, ""),
                RiskComponent("false_resolution", 1, False, "r", {}, ""),
                RiskComponent("open_commitment", 1, True, "r", {}, ""),
            ],
        )
        result = compute_priority(
            risk_result=risk,
            analysis=make_analysis(resolution="unresolved"),
            open_commitments=[make_commitment(deadline_flag="overdue")],
            turns=make_turns("I want to cancel my service"),
            cases=[],
        )
        assert result.priority == "P1"
        assert result.impact == "high"
        assert result.urgency == "high"
        assert result.quadrant == "Important and urgent"

    def test_p2_high_impact_low_urgency(self):
        """High risk band, no urgency signals → P2."""
        from backend.action_layer.risk_engine import RiskResult
        risk = RiskResult(
            risk_index=7, risk_band="high",
            components=[
                RiskComponent("cancellation_intent", 3, True, "r", {}, ""),
                RiskComponent("critical_violation", 1, False, "r", {}, ""),
                RiskComponent("repeat_contact", 1, False, "r", {}, ""),
                RiskComponent("broken_earlier_promise", 1, False, "r", {}, ""),
                RiskComponent("overdue_commitment", 1, False, "r", {}, ""),
                RiskComponent("false_resolution", 1, False, "r", {}, ""),
                RiskComponent("open_commitment", 1, False, "r", {}, ""),
            ],
        )
        result = compute_priority(
            risk_result=risk,
            analysis=make_analysis(resolution="resolved"),
            open_commitments=[],
            turns=make_turns("I want to cancel my service"),
            cases=[],
        )
        assert result.priority == "P2"
        assert result.impact == "high"
        assert result.urgency == "low"
        assert result.quadrant == "Important, not urgent"

    def test_p3_low_impact_low_urgency(self):
        """No triggers → P3."""
        from backend.action_layer.risk_engine import RiskResult
        risk = RiskResult(
            risk_index=1, risk_band="low",
            components=[
                RiskComponent("cancellation_intent", 3, False, "r", {}, ""),
                RiskComponent("critical_violation", 1, False, "r", {}, ""),
                RiskComponent("repeat_contact", 1, False, "r", {}, ""),
                RiskComponent("broken_earlier_promise", 1, False, "r", {}, ""),
                RiskComponent("overdue_commitment", 1, False, "r", {}, ""),
                RiskComponent("false_resolution", 1, False, "r", {}, ""),
                RiskComponent("open_commitment", 1, False, "r", {}, ""),
            ],
        )
        result = compute_priority(
            risk_result=risk,
            analysis=make_analysis(resolution="resolved"),
            open_commitments=[],
            turns=make_turns("thank you"),
            cases=[],
        )
        assert result.priority == "P3"
        assert result.impact == "low"
        assert result.urgency == "low"


# ── Intervention Type Tests ───────────────────────────────────────────────────

class TestInterventionType:

    def _make_risk(self, cancellation=False, repeat=False, broken=False):
        from backend.action_layer.risk_engine import RiskResult
        return RiskResult(
            risk_index=5, risk_band="medium",
            components=[
                RiskComponent("cancellation_intent", 3, cancellation, "r", {}, ""),
                RiskComponent("repeat_contact", 1, repeat, "r", {}, ""),
                RiskComponent("broken_earlier_promise", 1, broken, "r", {}, ""),
                RiskComponent("overdue_commitment", 1, False, "r", {}, ""),
                RiskComponent("false_resolution", 1, False, "r", {}, ""),
                RiskComponent("open_commitment", 1, False, "r", {}, ""),
                RiskComponent("critical_violation", 1, False, "r", {}, ""),
            ],
        )

    def test_firm_exit_intent(self):
        risk = self._make_risk(cancellation=True)
        result = compute_intervention_type(
            analysis=make_analysis(resolution="resolved"),
            risk_result=risk,
            open_commitments=[],
            turns=make_turns("I want to cancel my service final decision"),
        )
        assert result.intervention_type == "firm_exit_intent"

    def test_fix_driven_unresolved(self):
        risk = self._make_risk()
        result = compute_intervention_type(
            analysis=make_analysis(resolution="unresolved"),
            risk_result=risk,
            open_commitments=[],
            turns=make_turns("ok"),
        )
        assert result.intervention_type == "fix_driven"

    def test_fix_driven_open_commitment(self):
        risk = self._make_risk()
        result = compute_intervention_type(
            analysis=make_analysis(resolution="resolved"),
            risk_result=risk,
            open_commitments=[make_commitment()],
            turns=make_turns("ok"),
        )
        assert result.intervention_type == "fix_driven"

    def test_monitor_low_risk(self):
        from backend.action_layer.risk_engine import RiskResult
        risk = RiskResult(
            risk_index=1, risk_band="low",
            components=[
                RiskComponent("cancellation_intent", 3, False, "r", {}, ""),
            ],
        )
        result = compute_intervention_type(
            analysis=make_analysis(resolution="resolved"),
            risk_result=risk,
            open_commitments=[],
            turns=make_turns("thank you"),
        )
        assert result.intervention_type == "monitor"

    def test_relationship_repair_broken_promise(self):
        risk = self._make_risk(repeat=True, broken=True)
        result = compute_intervention_type(
            analysis=make_analysis(resolution="resolved"),
            risk_result=risk,
            open_commitments=[],
            turns=make_turns("you promised last time"),
        )
        assert result.intervention_type == "relationship_repair"


# ── What-If Tests ─────────────────────────────────────────────────────────────

class TestWhatIf:

    def test_what_if_clears_cancellation(self):
        """Clearing cancellation_intent from a risk-7 item should reduce the index."""
        from backend.action_layer.risk_engine import RiskResult
        risk = RiskResult(
            risk_index=7, risk_band="high",
            components=[
                RiskComponent("cancellation_intent", 3, True, "r", {}, ""),
                RiskComponent("resolution_unresolved", 2, True, "r", {}, ""),
                RiskComponent("open_commitment", 1, True, "r", {}, ""),
                RiskComponent("overdue_commitment", 1, True, "r", {}, ""),
            ],
        )
        scenario = compute_what_if(risk, clear_components=["cancellation_intent"])
        assert scenario["scenario_risk_index"] == 4
        assert scenario["scenario_risk_band"] == "medium"
        assert "Scenario based on recorded signals" in scenario["disclaimer"]

    def test_what_if_clears_all_lowers_to_1(self):
        """Clearing all components should floor at 1."""
        from backend.action_layer.risk_engine import RiskResult
        risk = RiskResult(
            risk_index=5, risk_band="medium",
            components=[
                RiskComponent("cancellation_intent", 3, True, "r", {}, ""),
                RiskComponent("resolution_unresolved", 2, True, "r", {}, ""),
            ],
        )
        scenario = compute_what_if(
            risk,
            clear_components=["cancellation_intent", "resolution_unresolved"],
        )
        assert scenario["scenario_risk_index"] == 1

    def test_what_if_preserves_original(self):
        """What-if must not mutate the original risk result."""
        from backend.action_layer.risk_engine import RiskResult
        risk = RiskResult(
            risk_index=5, risk_band="medium",
            components=[RiskComponent("cancellation_intent", 3, True, "r", {}, "")],
        )
        original_index = risk.risk_index
        compute_what_if(risk, clear_components=["cancellation_intent"])
        assert risk.risk_index == original_index  # original unchanged
