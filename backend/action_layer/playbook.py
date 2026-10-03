"""
backend/action_layer/playbook.py
Versioned playbook: maps intervention types to ordered recommended actions.

Label: "example playbook — owner review and approval required before production use"
Version: playbook_example_v1

Rules:
- Every recommendation shows its triggering signals with quotes.
- No promises of outcomes (existing prohibited-promise policy applies).
- No monetary values except explicit "within authority limit (placeholder values, labeled example)".
- Firm exit intent → graceful exit + later win-back, NOT heavy discounting.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

PLAYBOOK_RULES_VERSION = "playbook_example_v1"
PLAYBOOK_LABEL = "example playbook — owner review and approval required before production use"


@dataclass
class PlaybookAction:
    action_key: str
    rank: int
    title: str
    justification_template: str  # may contain {signal} placeholder
    constraint_note: str
    playbook_rule_id: str


# ── Playbook library ──────────────────────────────────────────────────────────
# Each intervention type maps to an ordered list of recommended actions.

PLAYBOOK: dict[str, list[PlaybookAction]] = {
    "fix_driven": [
        PlaybookAction(
            action_key="fulfil_open_commitment",
            rank=1,
            title="Fulfil or update the open commitment first",
            justification_template=(
                "An open commitment was recorded: {signal}. "
                "Resolving this is the highest-priority action — it is the root cause of the open item."
            ),
            constraint_note="Update the commitment status once fulfilled. Do not promise outcomes beyond your authority.",
            playbook_rule_id="fix_driven.1",
        ),
        PlaybookAction(
            action_key="callback_within_window",
            rank=2,
            title="Schedule a callback within the agreed window",
            justification_template=(
                "The issue remains {signal}. A proactive callback confirms the fix was completed."
            ),
            constraint_note="Call back within the configured callback window (admin-configurable, default 24 hours). Do not promise specific resolution times you cannot guarantee.",
            playbook_rule_id="fix_driven.2",
        ),
        PlaybookAction(
            action_key="verify_resolution",
            rank=3,
            title="Verify the issue is resolved to the customer's satisfaction",
            justification_template=(
                "Resolution was recorded as {signal}. Confirm with the customer that the fix is effective."
            ),
            constraint_note="Record the outcome. Do not mark as resolved until confirmed.",
            playbook_rule_id="fix_driven.3",
        ),
    ],
    "price_sensitive": [
        PlaybookAction(
            action_key="review_plan_options",
            rank=1,
            title="Review available plan options with the customer",
            justification_template=(
                "Customer expressed price sensitivity: {signal}. "
                "Present available plans without committing to a discount beyond your authority."
            ),
            constraint_note="Example: goodwill gesture only within stated authority limit (placeholder — owner must set actual limits). Do not promise discounts you cannot authorize.",
            playbook_rule_id="price_sensitive.1",
        ),
        PlaybookAction(
            action_key="clarify_billing",
            rank=2,
            title="Clarify the billing item in question",
            justification_template=(
                "Billing concern detected: {signal}. Ensure the charge is explained clearly."
            ),
            constraint_note="If an error is confirmed, escalate to billing. Do not issue credits without authorization.",
            playbook_rule_id="price_sensitive.2",
        ),
        PlaybookAction(
            action_key="escalate_if_unresolved",
            rank=3,
            title="Escalate to billing team if dispute is unresolved",
            justification_template=(
                "If the billing concern cannot be resolved at this level, escalate to the billing function."
            ),
            constraint_note="Escalate to the billing function. Do not promise a refund outcome.",
            playbook_rule_id="price_sensitive.3",
        ),
    ],
    "relationship_repair": [
        PlaybookAction(
            action_key="acknowledge_repeat_and_broken_promise",
            rank=1,
            title="Acknowledge the repeat issue and any broken promise",
            justification_template=(
                "Customer has a repeat contact or broken earlier promise: {signal}. "
                "Acknowledgment is the first step before offering solutions."
            ),
            constraint_note="Acknowledge genuinely. Do not make new promises you cannot keep. Do not over-commit.",
            playbook_rule_id="relationship_repair.1",
        ),
        PlaybookAction(
            action_key="fulfil_prior_commitment",
            rank=2,
            title="Prioritise fulfilling the outstanding prior commitment",
            justification_template=(
                "A prior commitment from a linked case remains open: {signal}. "
                "Fulfilling it is the most important relationship action."
            ),
            constraint_note="Coordinate with the team responsible. Update the commitment status when done.",
            playbook_rule_id="relationship_repair.2",
        ),
        PlaybookAction(
            action_key="goodwill_within_authority",
            rank=3,
            title="Consider a goodwill gesture within your stated authority",
            justification_template=(
                "Repeated failures have damaged trust. A goodwill gesture may help, within your authority limit."
            ),
            constraint_note="Example placeholder limit — owner must approve actual authority levels. Do not promise outcomes or specify amounts here.",
            playbook_rule_id="relationship_repair.3",
        ),
    ],
    "firm_exit_intent": [
        PlaybookAction(
            action_key="graceful_exit",
            rank=1,
            title="Offer a graceful exit process",
            justification_template=(
                "Customer has stated a firm decision to leave: {signal}. "
                "Do NOT apply heavy discounting — respect the decision."
            ),
            constraint_note="Process the exit professionally. Note the customer's reason for leaving.",
            playbook_rule_id="firm_exit.1",
        ),
        PlaybookAction(
            action_key="schedule_winback_contact",
            rank=2,
            title="Schedule a win-back contact for a later date",
            justification_template=(
                "After exit is processed, schedule a later win-back contact (example: 30–60 days). "
                "Timing is a placeholder — owner must set the actual policy."
            ),
            constraint_note="Do not contact immediately. Note the preferred contact time if the customer shares it.",
            playbook_rule_id="firm_exit.2",
        ),
        PlaybookAction(
            action_key="record_exit_reason",
            rank=3,
            title="Record the reason for exit accurately",
            justification_template=(
                "Accurate exit-reason data helps identify systemic issues. Record the specific reason stated."
            ),
            constraint_note="Use the standard exit-reason taxonomy. Do not guess.",
            playbook_rule_id="firm_exit.3",
        ),
    ],
    "monitor": [
        PlaybookAction(
            action_key="log_and_monitor",
            rank=1,
            title="Log the item and monitor — no immediate action required",
            justification_template=(
                "Risk is low ({signal}). No immediate intervention is required. Monitor for changes."
            ),
            constraint_note="Reassess if new signals emerge.",
            playbook_rule_id="monitor.1",
        ),
    ],
    "undetermined": [
        PlaybookAction(
            action_key="human_review",
            rank=1,
            title="Assign for human review — evidence insufficient for automatic recommendation",
            justification_template=(
                "Insufficient evidence to determine the appropriate intervention type. "
                "A supervisor should review the conversation directly."
            ),
            constraint_note="Do not act on automated recommendations until a human has reviewed.",
            playbook_rule_id="undetermined.1",
        ),
    ],
}


def get_recommendations(
    intervention_type: str,
    intervention_evidence: list[dict[str, Any]],
    risk_result_components: list[Any],  # RiskComponent list
) -> list[dict[str, Any]]:
    """
    Return ordered recommendations for the given intervention type.
    Each recommendation includes filled justification text and signal refs.
    """
    actions = PLAYBOOK.get(intervention_type, PLAYBOOK["undetermined"])

    # Build a signal summary string for template filling
    signal_parts = []
    for ev in intervention_evidence:
        if ev.get("phrase"):
            signal_parts.append(f'"{ev["phrase"]}"')
        elif ev.get("value"):
            signal_parts.append(str(ev["value"]))
        elif ev.get("commitment_id"):
            signal_parts.append(f"commitment {ev['commitment_id'][:8]}")
    signal_str = ", ".join(signal_parts) if signal_parts else "recorded signals"

    result = []
    for action in sorted(actions, key=lambda a: a.rank):
        justification = action.justification_template.replace("{signal}", signal_str)
        result.append({
            "rank": action.rank,
            "action_key": action.action_key,
            "title": action.title,
            "justification": justification,
            "signal_refs": intervention_evidence,
            "playbook_rule_id": action.playbook_rule_id,
            "constraint_note": action.constraint_note,
            "rules_version": PLAYBOOK_RULES_VERSION,
            "label": PLAYBOOK_LABEL,
        })
    return result
