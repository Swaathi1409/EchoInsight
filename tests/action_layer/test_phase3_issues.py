"""
tests/action_layer/test_phase3_issues.py

Phase 3 tests for recurring issue detection, prevention suggestions, and PDCA check.
All fixtures are SYNTHETIC — not real production data.
"""
from __future__ import annotations

from datetime import UTC, datetime, timedelta

from backend.action_layer.prevention_library import get_prevention_suggestions
from backend.action_layer.recurrence_engine import (
    compute_pdca_check,
    detect_recurring_issues,
)

# ── Helpers ───────────────────────────────────────────────────────────────────

AS_OF = datetime(2026, 10, 3, 12, 0, 0, tzinfo=UTC)


def make_conv(
    conv_id: str,
    reason: str,
    resolution: str = "unresolved",
    started_at: datetime | None = None,
    qa_score: float | None = None,
    sentiment: str = "neutral",
):
    started = started_at or AS_OF
    return {
        "analysis_id": f"a_{conv_id}",
        "conversation_id": conv_id,
        "version": 1,
        "resolution": resolution,
        "churn_risk": "low",
        "churn_signals": [],
        "false_resolution": False,
        "sentiment_trajectory": [{"sentiment": sentiment}],
        "reasons": [reason],
        "summary": "test",
        "prompt_version": "v1",
        "qa_score": qa_score,
        "conversation": {
            "id": conv_id,
            "source_id": conv_id,
            "agent_id": "agent-001",
            "team_id": "team-001",
            "started_at": started,
            "ended_at": started + timedelta(minutes=10),
            "channel": "voice",
        },
    }


def make_conv_set(
    reason: str,
    n: int,
    resolution: str = "unresolved",
    start_base: datetime | None = None,
    interval_hours: int = 6,
) -> list:
    base = start_base or (AS_OF - timedelta(days=14))
    return [
        make_conv(
            conv_id=f"{reason[:8]}_{i:03d}",
            reason=reason,
            resolution=resolution,
            started_at=base + timedelta(hours=i * interval_hours),
        )
        for i in range(n)
    ]


# ── Recurrence Detection Tests ────────────────────────────────────────────────

class TestRecurrenceDetection:

    def test_no_issues_below_min_volume(self):
        """SYNTHETIC: 2 conversations for a reason → below min_volume=3, no issue."""
        convs = make_conv_set("billing dispute", n=2)
        result = detect_recurring_issues(
            analyzed_conversations=convs,
            conversations_with_turns={},
            as_of=AS_OF,
            min_volume=3,
        )
        assert result == []

    def test_detects_high_unresolved_rate(self):
        """SYNTHETIC: 5 unresolved conversations for same reason → issue detected."""
        convs = make_conv_set("network outage", n=5, resolution="unresolved")
        result = detect_recurring_issues(
            analyzed_conversations=convs,
            conversations_with_turns={},
            as_of=AS_OF,
            min_volume=3,
            min_unresolved_rate=0.4,
        )
        assert len(result) >= 1
        issue = next(r for r in result if r["reason_label"] == "network outage")
        assert issue["unresolved_rate"] >= 0.4
        assert any("unresolved_rate" in t for t in issue["triggered_thresholds"])

    def test_detects_trending_up(self):
        """SYNTHETIC: Previous window 2, current window 5 → trend up detected."""
        # Previous window: 2 conversations (old dates)
        prev_base = AS_OF - timedelta(days=20)
        prev_convs = make_conv_set("billing dispute", n=2, resolution="unresolved",
                                   start_base=prev_base, interval_hours=24)
        # Current window: 5 conversations (recent)
        curr_base = AS_OF - timedelta(days=6)
        curr_convs = make_conv_set("billing dispute", n=5, resolution="unresolved",
                                   start_base=curr_base, interval_hours=12)
        all_convs = prev_convs + curr_convs
        result = detect_recurring_issues(
            analyzed_conversations=all_convs,
            conversations_with_turns={},
            as_of=AS_OF,
            min_volume=3,
        )
        issue = next((r for r in result if r["reason_label"] == "billing dispute"), None)
        assert issue is not None
        assert issue["trend_direction"] == "up"

    def test_resolved_conversations_not_flagged(self):
        """SYNTHETIC: 5 resolved conversations, low unresolved rate → no issue."""
        convs = make_conv_set("verification", n=6, resolution="resolved")
        result = detect_recurring_issues(
            analyzed_conversations=convs,
            conversations_with_turns={},
            as_of=AS_OF,
            min_volume=3,
            min_unresolved_rate=0.4,   # resolved → 0% unresolved rate
            min_trend_pct=0.20,         # trend must be ≥20%
            min_escalation_share=0.3,   # escalation 0%
        )
        # unresolved_rate=0 < 0.4, escalation_share=0 < 0.3, trend will be flat/down
        # → no threshold met → no issue
        verification_issue = next(
            (r for r in result if r["reason_label"] == "verification"), None
        )
        assert verification_issue is None, (
            f"Expected no issue for resolved conversations but got: "
            f"{verification_issue}"
        )

    def test_multiple_reasons_grouped_correctly(self):
        """SYNTHETIC: Two different reasons each with enough volume → two separate issue groups."""
        # Use enough conversations so each reason has >= min_volume in current window
        billing = make_conv_set(
            "billing dispute", n=8, resolution="unresolved",
            start_base=AS_OF - timedelta(days=6), interval_hours=6
        )
        network = make_conv_set(
            "network outage", n=6, resolution="unresolved",
            start_base=AS_OF - timedelta(days=5), interval_hours=8
        )
        result = detect_recurring_issues(
            analyzed_conversations=billing + network,
            conversations_with_turns={},
            as_of=AS_OF,
            min_volume=3,
        )
        labels = {r["reason_label"] for r in result}
        assert "billing dispute" in labels, f"billing dispute not in {labels}"
        assert "network outage" in labels, f"network outage not in {labels}"

    def test_result_has_required_fields(self):
        """SYNTHETIC: Result dict has all required fields."""
        convs = make_conv_set("network outage", n=5, resolution="unresolved")
        result = detect_recurring_issues(
            analyzed_conversations=convs,
            conversations_with_turns={},
            as_of=AS_OF,
        )
        if result:
            issue = result[0]
            for field in [
                "reason_label", "volume", "unresolved_rate",
                "trend_direction", "triggered_thresholds", "rules_version",
            ]:
                assert field in issue, f"Missing field: {field}"

    def test_sorted_by_volume_descending(self):
        """SYNTHETIC: Results sorted by volume descending."""
        billing = make_conv_set("billing dispute", n=10, resolution="unresolved")
        network = make_conv_set("network outage", n=4, resolution="unresolved")
        result = detect_recurring_issues(
            analyzed_conversations=billing + network,
            conversations_with_turns={},
            as_of=AS_OF,
            min_volume=3,
        )
        if len(result) >= 2:
            assert result[0]["volume"] >= result[1]["volume"]


# ── Prevention Suggestion Tests ───────────────────────────────────────────────

class TestPreventionSuggestions:

    def make_issue(
        self,
        reason_label: str,
        unresolved_rate: float = 0.5,
        trend_direction: str = "up",
        escalation_share: float = 0.1,
        volume: int = 5,
    ):
        return {
            "reason_label": reason_label,
            "unresolved_rate": unresolved_rate,
            "trend_direction": trend_direction,
            "escalation_share": escalation_share,
            "volume": volume,
            "n": volume,
            "trend_pct_change": 0.25,
            "avg_qa_score": 70.0,
            "example_quotes": [],
            "triggered_thresholds": [],
            "window_start": None,
            "window_end": None,
        }

    def test_network_issue_yields_suggestion(self):
        """SYNTHETIC: network outage issue → network suggestion returned."""
        issue = self.make_issue("network outage")
        suggestions = get_prevention_suggestions(issue)
        assert len(suggestions) > 0
        rule_ids = [s["prevention_rule_id"] for s in suggestions]
        assert any("network" in r for r in rule_ids)

    def test_billing_issue_yields_suggestion(self):
        """SYNTHETIC: billing dispute → billing suggestion returned."""
        issue = self.make_issue("billing dispute")
        suggestions = get_prevention_suggestions(issue)
        assert len(suggestions) > 0

    def test_all_suggestions_have_evidence(self):
        """SYNTHETIC: every suggestion must have an evidence dict."""
        issue = self.make_issue("network outage")
        suggestions = get_prevention_suggestions(issue)
        for s in suggestions:
            assert "evidence" in s
            assert s["evidence"].get("n") is not None

    def test_all_suggestions_labeled_hypothesis(self):
        """SYNTHETIC: every suggestion must carry the hypothesis label."""
        issue = self.make_issue("billing dispute")
        suggestions = get_prevention_suggestions(issue)
        for s in suggestions:
            assert s["label"] == "Hypothesis for human validation"

    def test_no_suggestion_without_evidence(self):
        """SYNTHETIC: low unresolved rate, no trend up → general suggestions suppressed."""
        issue = self.make_issue("unknown_reason_xyz", unresolved_rate=0.1,
                               trend_direction="flat", escalation_share=0.05)
        suggestions = get_prevention_suggestions(issue)
        # general catch-all requires ≥60% unresolved rate
        # reason-keyword rules won't match "unknown_reason_xyz"
        assert len(suggestions) == 0


# ── PDCA Check Tests ──────────────────────────────────────────────────────────

class TestPDCACheck:

    def test_insufficient_data_when_too_few_conversations(self):
        """SYNTHETIC: 2 post-implementation conversations → insufficient data."""
        impl_date = AS_OF - timedelta(days=10)
        post_convs = [
            make_conv("post_001", "billing dispute", resolution="resolved",
                      started_at=impl_date + timedelta(days=1)),
            make_conv("post_002", "billing dispute", resolution="resolved",
                      started_at=impl_date + timedelta(days=2)),
        ]
        result = compute_pdca_check(
            baseline_metrics={"n": 10, "unresolved_rate": 0.6},
            post_conversations=post_convs,
            reason_label="billing dispute",
            implementation_date=impl_date,
            as_of=AS_OF,
            min_post_conversations=5,
            min_post_days=7,
        )
        assert result["sufficient_data"] is False
        assert "not enough" in result["message"].lower()

    def test_insufficient_data_when_too_few_days(self):
        """SYNTHETIC: 10 conversations but only 3 days elapsed → insufficient."""
        impl_date = AS_OF - timedelta(days=3)
        post_convs = [
            make_conv(f"post_{i:03d}", "billing dispute", resolution="resolved",
                      started_at=impl_date + timedelta(hours=i * 6))
            for i in range(10)
        ]
        result = compute_pdca_check(
            baseline_metrics={"n": 10, "unresolved_rate": 0.6},
            post_conversations=post_convs,
            reason_label="billing dispute",
            implementation_date=impl_date,
            as_of=AS_OF,
            min_post_conversations=5,
            min_post_days=7,
        )
        assert result["sufficient_data"] is False

    def test_sufficient_data_shows_improvement(self):
        """SYNTHETIC: 10 resolved post-conversations → improvement shown."""
        impl_date = AS_OF - timedelta(days=14)
        post_convs = [
            make_conv(f"post_{i:03d}", "network outage", resolution="resolved",
                      started_at=impl_date + timedelta(days=i))
            for i in range(1, 11)
        ]
        result = compute_pdca_check(
            baseline_metrics={"n": 10, "unresolved_rate": 0.6},
            post_conversations=post_convs,
            reason_label="network outage",
            implementation_date=impl_date,
            as_of=AS_OF,
            min_post_conversations=5,
            min_post_days=7,
        )
        assert result["sufficient_data"] is True
        assert result["post_n"] == 10
        check = result["check_results"].get("unresolved_rate", {})
        assert check.get("post_value", 1.0) == 0.0  # all resolved
        assert check.get("direction") == "improved"
        # Must include caveat about correlation
        assert "indicative" in result["caveats"].lower()

    def test_check_ignores_pre_implementation_conversations(self):
        """SYNTHETIC: Only post-implementation conversations counted."""
        impl_date = AS_OF - timedelta(days=10)
        pre_convs = [
            make_conv(f"pre_{i:03d}", "billing dispute", resolution="unresolved",
                      started_at=impl_date - timedelta(days=i + 1))
            for i in range(5)
        ]
        post_convs = [
            make_conv(f"post_{i:03d}", "billing dispute", resolution="resolved",
                      started_at=impl_date + timedelta(days=i + 1))
            for i in range(8)
        ]
        result = compute_pdca_check(
            baseline_metrics={"n": 5, "unresolved_rate": 1.0},
            post_conversations=pre_convs + post_convs,
            reason_label="billing dispute",
            implementation_date=impl_date,
            as_of=AS_OF,
            min_post_conversations=5,
            min_post_days=7,
        )
        assert result["sufficient_data"] is True
        assert result["post_n"] == 8  # only 8 post, not 13
