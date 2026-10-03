"""
backend/action_layer/prevention_library.py
Versioned prevention suggestions library.

Maps issue patterns to evidence-backed suggestions with owner functions.
Label: "Hypothesis for human validation"
Version: prevention_example_v1

Rules:
- Every suggestion must be backed by evidence (counts, trend, unresolved rate, quotes).
- Never show a suggestion without evidence.
- Suggestions are hypotheses, not conclusions.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

PREVENTION_RULES_VERSION = "prevention_example_v1"
PREVENTION_LABEL = "Hypothesis for human validation"


@dataclass
class PreventionRule:
    rule_id: str
    reason_keywords: list[str]  # any of these in reason_label triggers this rule
    condition_fn: Any  # callable(issue_data) -> bool
    suggestion_text: str
    suggested_owner: str


# ── Prevention library rules ──────────────────────────────────────────────────

def _has_high_unresolved(issue: dict[str, Any], threshold: float = 0.4) -> bool:
    return issue.get("unresolved_rate", 0.0) >= threshold


def _is_trending_up(issue: dict[str, Any]) -> bool:
    return issue.get("trend_direction") == "up"


def _has_high_escalation(issue: dict[str, Any], threshold: float = 0.3) -> bool:
    return issue.get("escalation_share", 0.0) >= threshold


PREVENTION_RULES: list[PreventionRule] = [
    # Network / outage issues
    PreventionRule(
        rule_id="prev_network_proactive",
        reason_keywords=["network", "outage", "signal", "coverage", "no service", "dropped"],
        condition_fn=lambda i: _has_high_unresolved(i) or _is_trending_up(i),
        suggestion_text=(
            "Rising network-related contacts with a high unresolved rate suggest customers "
            "are not being informed proactively about outages. "
            "Consider: proactive outage notifications before customers call, "
            "and a faster escalation path to network operations when an outage is confirmed."
        ),
        suggested_owner="Network Operations",
    ),
    PreventionRule(
        rule_id="prev_network_escalation",
        reason_keywords=["network", "outage", "signal", "coverage", "no service"],
        condition_fn=lambda i: _has_high_escalation(i),
        suggestion_text=(
            "A high share of network contacts are escalated, indicating agents may lack "
            "the tools or authority to resolve network issues at first contact. "
            "Consider: empowering frontline agents with real-time network status tools "
            "and clear escalation criteria."
        ),
        suggested_owner="Contact Centre Operations",
    ),
    # Billing issues
    PreventionRule(
        rule_id="prev_billing_clarity",
        reason_keywords=["bill", "billing", "charge", "invoice", "payment", "overcharge"],
        condition_fn=lambda i: _has_high_unresolved(i),
        suggestion_text=(
            "Repeated billing-related contacts with unresolved outcomes suggest customers "
            "find bills unclear or are receiving incorrect charges. "
            "Consider: clearer bill explanations, a self-service dispute portal, "
            "and a review of the most common charge types customers question."
        ),
        suggested_owner="Billing",
    ),
    # Verification failures
    PreventionRule(
        rule_id="prev_verification_simplify",
        reason_keywords=["verif", "authentication", "security question", "id check"],
        condition_fn=lambda i: _is_trending_up(i) or _has_high_unresolved(i),
        suggestion_text=(
            "Frequent verification failures are trending upward. "
            "Consider: a simplified verification step that reduces call abandonment "
            "while maintaining security standards. Review with the security and process team."
        ),
        suggested_owner="Process Owner / Security",
    ),
    # Callback / promise failures
    PreventionRule(
        rule_id="prev_callback_queue",
        reason_keywords=["callback", "call back", "called back", "promised", "no one called"],
        condition_fn=lambda i: _has_high_unresolved(i) or _is_trending_up(i),
        suggestion_text=(
            "Repeated broken callback promises are a key driver of repeat contacts. "
            "Consider: a managed callback queue with deadline tracking, "
            "automatic reminders to agents, and escalation when a callback becomes overdue."
        ),
        suggested_owner="Contact Centre Operations",
    ),
    # Cancellation / churn intent
    PreventionRule(
        rule_id="prev_churn_early_intervention",
        reason_keywords=["cancel", "cancellation", "switch", "leave", "port"],
        condition_fn=lambda i: _is_trending_up(i),
        suggestion_text=(
            "Cancellation-intent contacts are trending upward. "
            "Consider: an early-intervention programme that identifies at-risk customers "
            "before they call to cancel, and targeted retention offers within defined authority limits."
        ),
        suggested_owner="Retention / Commercial",
    ),
    # General high unresolved catch-all
    PreventionRule(
        rule_id="prev_general_unresolved",
        reason_keywords=[],  # applies to any reason
        condition_fn=lambda i: i.get("unresolved_rate", 0.0) >= 0.6,  # ≥60% threshold
        suggestion_text=(
            "This issue has a very high unresolved rate. "
            "Consider: a structured root-cause analysis session with frontline agents "
            "to identify whether the barrier is process, system, policy, or knowledge-based."
        ),
        suggested_owner="Process Owner",
    ),
]


def _reason_matches_keywords(reason_label: str, keywords: list[str]) -> bool:
    """Return True if any keyword appears in the reason label (case-insensitive)."""
    if not keywords:
        return True  # empty keyword list = catch-all
    r = reason_label.lower()
    return any(kw.lower() in r for kw in keywords)


def get_prevention_suggestions(
    issue: dict[str, Any],
) -> list[dict[str, Any]]:
    """
    Return prevention suggestions for a given recurring issue.
    Each suggestion includes its evidence block.
    Only suggestions with matching evidence are returned.
    """
    reason_label = issue.get("reason_label", "")
    suggestions = []

    for rule in PREVENTION_RULES:
        if not _reason_matches_keywords(reason_label, rule.reason_keywords):
            continue
        if not rule.condition_fn(issue):
            continue

        # Build evidence block from issue data
        evidence: dict[str, Any] = {
            "n": issue.get("n", issue.get("volume", 0)),
            "unresolved_rate": issue.get("unresolved_rate"),
            "trend_direction": issue.get("trend_direction"),
            "trend_pct_change": issue.get("trend_pct_change"),
            "escalation_share": issue.get("escalation_share"),
            "avg_qa_score": issue.get("avg_qa_score"),
            "example_quotes": issue.get("example_quotes", [])[:2],
            "triggered_thresholds": issue.get("triggered_thresholds", []),
            "window_start": str(issue.get("window_start", "")),
            "window_end": str(issue.get("window_end", "")),
        }

        suggestions.append({
            "prevention_rule_id": rule.rule_id,
            "rules_version": PREVENTION_RULES_VERSION,
            "label": PREVENTION_LABEL,
            "suggestion_text": rule.suggestion_text,
            "suggested_owner": rule.suggested_owner,
            "evidence": evidence,
            "reason_label": reason_label,
        })

    return suggestions
