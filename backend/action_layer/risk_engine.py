"""
backend/action_layer/risk_engine.py
Deterministic Risk Index and Priority computation for the Action Intelligence Layer.

Risk Index: 1–10 (integer), computed from weighted components.
Priority: P1/P2/P3 derived from impact + urgency quadrant.
Intervention type: deterministic from evidence.

All rules are versioned. This version: risk_example_v1 / priority_example_v1.
Label: "example policy — owner review required before production use"

SAFETY:
- Reads only from stored analysis dicts (output of CoreRepository).
- Never triggers model calls.
- Never writes to any table.
- Every component references a verifiable evidence field.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from backend.action_layer.config import DEFAULT_COMMITMENT_DUE_SOON_HOURS
from backend.action_layer.phrase_lists import (
    ANGER_PHRASES,
    BILLING_REASON_PHRASES,
    CANCELLATION_INTENT_PHRASES,
    DECLINED_OFFER_PHRASES,
    DEFAULT_HIGH_IMPACT_REASONS,
    FIRM_EXIT_PHRASES,
    PHRASE_LISTS_VERSION,
    PRICE_SENSITIVE_PHRASES,
    TIME_PRESSURE_PHRASES,
    find_matching_phrases,
)

RISK_RULES_VERSION = "risk_example_v1"
PRIORITY_RULES_VERSION = "priority_example_v1"
RISK_RULES_LABEL = "example policy — owner review required before production use"

# ── Risk component weights ─────────────────────────────────────────────────────
# Total is capped at 10, floor 1.
WEIGHT_CANCELLATION_INTENT = 3
WEIGHT_SENTIMENT_ANGRY = 2
WEIGHT_SENTIMENT_FRUSTRATED = 1
WEIGHT_RESOLUTION_UNRESOLVED = 2
WEIGHT_RESOLUTION_PENDING = 1
WEIGHT_RESOLUTION_ESCALATED = 1
WEIGHT_OPEN_COMMITMENT = 1
WEIGHT_OVERDUE_COMMITMENT = 1  # additional on top of open commitment
WEIGHT_FALSE_RESOLUTION = 1
WEIGHT_CRITICAL_VIOLATION = 1
WEIGHT_REPEAT_CONTACT = 1
WEIGHT_BROKEN_EARLIER_PROMISE = 1  # additional on top of repeat contact


@dataclass
class RiskComponent:
    name: str
    points: int
    triggered: bool
    rule: str
    evidence_ref: dict[str, Any]  # {type, value, quote}
    description: str


@dataclass
class RiskResult:
    risk_index: int
    risk_band: str  # low | medium | high
    components: list[RiskComponent]
    rules_version: str = RISK_RULES_VERSION
    disclaimer: str = (
        "This Risk Index is NOT a probability. It reflects a weighted sum "
        "of recorded signals. See the breakdown for details."
    )
    label: str = RISK_RULES_LABEL
    evidence_complete: bool = True
    evidence_incomplete_reasons: list[str] = field(default_factory=list)


@dataclass
class ImpactUrgencyResult:
    impact: str   # high | low
    urgency: str  # high | low
    priority: str  # P1 | P2 | P3
    quadrant: str
    impact_reasons: list[str]
    urgency_reasons: list[str]
    rules_version: str = PRIORITY_RULES_VERSION


@dataclass
class InterventionResult:
    intervention_type: str
    matched_phrases: list[str]
    evidence: list[dict[str, Any]]
    rules_version: str = PHRASE_LISTS_VERSION


# ── Sentiment helper ───────────────────────────────────────────────────────────

def _end_sentiment(sentiment_trajectory: list[dict[str, Any]]) -> str:
    """Return the sentiment label of the last turn with a sentiment entry."""
    if not sentiment_trajectory:
        return "neutral"
    for entry in reversed(sentiment_trajectory):
        label = entry.get("sentiment", "neutral")
        if label:
            return label.lower()
    return "neutral"


def _customer_turn_texts(turns: list[dict[str, Any]]) -> str:
    """Concatenate all customer turn texts for phrase searching."""
    return " ".join(
        t.get("text_redacted", "") for t in turns
        if t.get("speaker", "").lower() in ("customer", "user", "caller")
    )


def _find_phrase_evidence(
    text: str,
    phrases: list[str],
    turn_id: str = "",
    evidence_type: str = "phrase_match",
) -> list[dict[str, Any]]:
    """Return evidence dicts for each matched phrase."""
    matches = find_matching_phrases(text, phrases)
    return [
        {"type": evidence_type, "phrase": m, "turn_id": turn_id}
        for m in matches
    ]


# ── Risk Index computation ─────────────────────────────────────────────────────

def compute_risk_index(
    *,
    analysis: dict[str, Any],
    commitments: list[dict[str, Any]],
    qa_result: dict[str, Any] | None,
    turns: list[dict[str, Any]],
    cases: list[dict[str, Any]],
    case_other_commitments: list[dict[str, Any]],
    as_of: datetime,
    due_soon_hours: int = DEFAULT_COMMITMENT_DUE_SOON_HOURS,
) -> RiskResult:
    """
    Compute the Risk Index from stored analysis results.
    Returns a RiskResult with full component breakdown and evidence references.
    """
    components: list[RiskComponent] = []
    customer_text = _customer_turn_texts(turns)
    evidence_incomplete_reasons: list[str] = []

    # ── Component 1: Explicit cancellation / switching intent ─────────────────
    cancellation_matches = find_matching_phrases(customer_text, CANCELLATION_INTENT_PHRASES)
    # Also check churn_signals from analysis
    churn_signals: list[str] = analysis.get("churn_signals", [])
    churn_has_intent = any(
        any(p in s.lower() for p in ["cancel", "switch", "leave", "port"])
        for s in churn_signals
    )
    cancellation_triggered = bool(cancellation_matches) or (
        analysis.get("churn_risk") == "high" and churn_has_intent
    )
    quote = cancellation_matches[0] if cancellation_matches else (
        churn_signals[0] if churn_has_intent and churn_signals else ""
    )
    if cancellation_triggered and not quote:
        # churn_risk=high but no verifiable quote → incomplete
        evidence_incomplete_reasons.append(
            "cancellation_intent: churn_risk=high but no verifiable turn quote found"
        )
        cancellation_triggered = False  # omit unverified signal per rule §9

    components.append(RiskComponent(
        name="cancellation_intent",
        points=WEIGHT_CANCELLATION_INTENT,
        triggered=cancellation_triggered,
        rule=f"Explicit switching or cancellation intent stated by the customer (weight {WEIGHT_CANCELLATION_INTENT})",
        evidence_ref={"type": "phrase_match", "quote": quote},
        description="Customer stated explicit intent to cancel or switch provider.",
    ))

    # ── Component 2: End-of-call sentiment ────────────────────────────────────
    end_sent = _end_sentiment(analysis.get("sentiment_trajectory", []))
    sent_angry = end_sent in ("angry", "very_negative", "very negative")
    sent_frustrated = end_sent in ("frustrated", "negative", "dissatisfied")

    components.append(RiskComponent(
        name="sentiment_angry",
        points=WEIGHT_SENTIMENT_ANGRY,
        triggered=sent_angry,
        rule=f"Customer sentiment at end of call: angry (weight {WEIGHT_SENTIMENT_ANGRY})",
        evidence_ref={"type": "sentiment_trajectory", "value": end_sent},
        description=f"End-of-call sentiment: {end_sent}",
    ))
    components.append(RiskComponent(
        name="sentiment_frustrated",
        points=WEIGHT_SENTIMENT_FRUSTRATED,
        triggered=sent_frustrated and not sent_angry,
        rule=f"Customer sentiment at end of call: frustrated (weight {WEIGHT_SENTIMENT_FRUSTRATED})",
        evidence_ref={"type": "sentiment_trajectory", "value": end_sent},
        description=f"End-of-call sentiment: {end_sent}",
    ))

    # ── Component 3: Final resolution ─────────────────────────────────────────
    resolution = analysis.get("resolution", "").lower()
    res_unresolved = resolution == "unresolved"
    res_pending = resolution in ("pending", "partially_resolved")
    res_escalated = resolution == "escalated"

    components.append(RiskComponent(
        name="resolution_unresolved",
        points=WEIGHT_RESOLUTION_UNRESOLVED,
        triggered=res_unresolved,
        rule=f"Final resolution: unresolved (weight {WEIGHT_RESOLUTION_UNRESOLVED})",
        evidence_ref={"type": "analysis_field", "field": "resolution", "value": resolution},
        description=f"Issue not resolved at end of call (resolution={resolution}).",
    ))
    components.append(RiskComponent(
        name="resolution_pending",
        points=WEIGHT_RESOLUTION_PENDING,
        triggered=res_pending,
        rule=f"Final resolution: pending/partially resolved (weight {WEIGHT_RESOLUTION_PENDING})",
        evidence_ref={"type": "analysis_field", "field": "resolution", "value": resolution},
        description=f"Issue partially or pending resolution (resolution={resolution}).",
    ))
    components.append(RiskComponent(
        name="resolution_escalated",
        points=WEIGHT_RESOLUTION_ESCALATED,
        triggered=res_escalated and not res_unresolved,
        rule=f"Final resolution: escalated and not resolved (weight {WEIGHT_RESOLUTION_ESCALATED})",
        evidence_ref={"type": "analysis_field", "field": "resolution", "value": resolution},
        description=f"Call escalated without resolution (resolution={resolution}).",
    ))

    # ── Component 4: Open and overdue commitments ─────────────────────────────
    open_commitments = [
        c for c in commitments
        if c.get("status") not in ("completed", "cancelled")
    ]
    has_open = len(open_commitments) > 0

    # Overdue: commitment has a deadline_flag of 'overdue' or deadline text passed as_of
    def _is_overdue(c: dict[str, Any]) -> bool:
        if c.get("deadline_flag") == "overdue":
            return True
        # Cannot reliably parse free-text deadlines; rely on deadline_flag
        return False

    has_overdue = any(_is_overdue(c) for c in open_commitments)
    overdue_commit = next((c for c in open_commitments if _is_overdue(c)), None)

    components.append(RiskComponent(
        name="open_commitment",
        points=WEIGHT_OPEN_COMMITMENT,
        triggered=has_open,
        rule=f"Open commitment present (weight {WEIGHT_OPEN_COMMITMENT})",
        evidence_ref={
            "type": "commitment",
            "count": len(open_commitments),
            "commitment_id": open_commitments[0].get("commitment_id", "") if open_commitments else "",
        },
        description=f"{len(open_commitments)} open commitment(s) found.",
    ))
    components.append(RiskComponent(
        name="overdue_commitment",
        points=WEIGHT_OVERDUE_COMMITMENT,
        triggered=has_overdue,
        rule=f"Any commitment overdue at the as-of time (+{WEIGHT_OVERDUE_COMMITMENT} additional)",
        evidence_ref={
            "type": "commitment",
            "commitment_id": overdue_commit.get("commitment_id", "") if overdue_commit else "",
            "deadline_flag": overdue_commit.get("deadline_flag", "") if overdue_commit else "",
        },
        description="At least one commitment is overdue at the as-of time.",
    ))

    # ── Component 5: False resolution flag ───────────────────────────────────
    false_res = bool(analysis.get("false_resolution", False))
    components.append(RiskComponent(
        name="false_resolution",
        points=WEIGHT_FALSE_RESOLUTION,
        triggered=false_res,
        rule=f"False-resolution flag raised (weight {WEIGHT_FALSE_RESOLUTION})",
        evidence_ref={
            "type": "analysis_field",
            "field": "false_resolution",
            "reason": analysis.get("false_resolution_reason", ""),
        },
        description="Detector flagged a false resolution.",
    ))

    # ── Component 6: Critical compliance violation ────────────────────────────
    crit_violation = bool(qa_result.get("critical_violation", False)) if qa_result else False
    components.append(RiskComponent(
        name="critical_violation",
        points=WEIGHT_CRITICAL_VIOLATION,
        triggered=crit_violation,
        rule=f"Critical compliance violation confirmed (weight {WEIGHT_CRITICAL_VIOLATION})",
        evidence_ref={"type": "qa_result", "critical_violation": crit_violation},
        description="QA found a confirmed critical compliance violation.",
    ))

    # ── Component 7: Repeat contact / broken earlier promise ─────────────────
    has_case = len(cases) > 0
    has_broken_promise_in_case = False
    if has_case and case_other_commitments:
        # Earlier promises in the case that are still open/unfulfilled
        broken = [
            c for c in case_other_commitments
            if c.get("status") not in ("completed", "cancelled")
        ]
        has_broken_promise_in_case = len(broken) > 0

    components.append(RiskComponent(
        name="repeat_contact",
        points=WEIGHT_REPEAT_CONTACT,
        triggered=has_case,
        rule=f"Repeat contact in an explicitly linked case (weight {WEIGHT_REPEAT_CONTACT})",
        evidence_ref={
            "type": "case_link",
            "case_count": len(cases),
            "case_id": cases[0].get("case_id", "") if cases else "",
        },
        description=f"Conversation is part of {len(cases)} linked case(s).",
    ))
    components.append(RiskComponent(
        name="broken_earlier_promise",
        points=WEIGHT_BROKEN_EARLIER_PROMISE,
        triggered=has_broken_promise_in_case,
        rule=f"Earlier promise in the case still open or unfulfilled (+{WEIGHT_BROKEN_EARLIER_PROMISE} additional)",
        evidence_ref={
            "type": "case_commitment",
            "open_prior_commitments": len(
                [c for c in case_other_commitments
                 if c.get("status") not in ("completed", "cancelled")]
            ) if case_other_commitments else 0,
        },
        description="A prior commitment in the linked case is still open.",
    ))

    # ── Sum and clamp ─────────────────────────────────────────────────────────
    raw_total = sum(c.points for c in components if c.triggered)
    risk_index = max(1, min(10, raw_total))

    # Band
    if risk_index <= 3:
        band = "low"
    elif risk_index <= 6:
        band = "medium"
    else:
        band = "high"

    return RiskResult(
        risk_index=risk_index,
        risk_band=band,
        components=components,
        evidence_complete=len(evidence_incomplete_reasons) == 0,
        evidence_incomplete_reasons=evidence_incomplete_reasons,
    )


# ── Impact / Urgency / Priority ────────────────────────────────────────────────

def compute_priority(
    *,
    risk_result: RiskResult,
    analysis: dict[str, Any],
    open_commitments: list[dict[str, Any]],
    turns: list[dict[str, Any]],
    cases: list[dict[str, Any]],
    high_impact_reasons: list[str] | None = None,
    due_soon_hours: int = DEFAULT_COMMITMENT_DUE_SOON_HOURS,
) -> ImpactUrgencyResult:
    """Compute P1/P2/P3 from impact and urgency."""
    if high_impact_reasons is None:
        high_impact_reasons = DEFAULT_HIGH_IMPACT_REASONS

    impact_reasons: list[str] = []
    urgency_reasons: list[str] = []

    # ── IMPACT ────────────────────────────────────────────────────────────────
    # High impact if ANY of:
    # 1. Risk band is high
    if risk_result.risk_band == "high":
        impact_reasons.append("Risk band is high")

    # 2. Confirmed critical violation
    crit = next((c for c in risk_result.components if c.name == "critical_violation"), None)
    if crit and crit.triggered:
        impact_reasons.append("Confirmed critical compliance violation")

    # 3. Repeat contact or broken earlier promise
    repeat = next((c for c in risk_result.components if c.name == "repeat_contact"), None)
    broken = next((c for c in risk_result.components if c.name == "broken_earlier_promise"), None)
    if (repeat and repeat.triggered) or (broken and broken.triggered):
        impact_reasons.append("Repeat contact or broken earlier promise in linked case")

    # 4. Reason on the high-impact list
    reasons = analysis.get("reasons", [])
    customer_text = _customer_turn_texts(turns)
    for reason in reasons:
        r_lower = reason.lower()
        for hi in high_impact_reasons:
            if hi.lower() in r_lower or r_lower in hi.lower():
                impact_reasons.append(f"Call reason '{reason}' is on the high-impact list")
                break
    # Also check cancellation intent phrases in customer text
    if find_matching_phrases(customer_text, CANCELLATION_INTENT_PHRASES):
        if "Cancellation intent phrase detected in customer turns" not in impact_reasons:
            impact_reasons.append("Cancellation intent phrase detected in customer turns")

    impact = "high" if impact_reasons else "low"

    # ── URGENCY ───────────────────────────────────────────────────────────────
    # High urgency if ANY of:
    # 1. Overdue commitment
    overdue = next((c for c in risk_result.components if c.name == "overdue_commitment"), None)
    if overdue and overdue.triggered:
        urgency_reasons.append("Commitment is overdue at as-of time")

    # 2. Commitment due within configured window
    due_soon = [
        c for c in open_commitments
        if c.get("deadline_flag") in ("due_soon", "urgent")
    ]
    if due_soon:
        urgency_reasons.append(
            f"Commitment due within {due_soon_hours}h (deadline_flag=due_soon/urgent)"
        )

    # 3. Explicit time pressure in customer turns
    time_phrases = find_matching_phrases(customer_text, TIME_PRESSURE_PHRASES)
    if time_phrases:
        urgency_reasons.append(
            f"Explicit time pressure: '{time_phrases[0]}'"
        )

    # 4. False resolution + open commitment
    false_res_comp = next(
        (c for c in risk_result.components if c.name == "false_resolution"), None
    )
    open_commit_comp = next(
        (c for c in risk_result.components if c.name == "open_commitment"), None
    )
    if (false_res_comp and false_res_comp.triggered and
            open_commit_comp and open_commit_comp.triggered):
        urgency_reasons.append("False-resolution flag raised with an open commitment")

    urgency = "high" if urgency_reasons else "low"

    # ── Priority mapping ──────────────────────────────────────────────────────
    if impact == "high" and urgency == "high":
        priority = "P1"
        quadrant = "Important and urgent"
    elif impact == "high" and urgency == "low":
        priority = "P2"
        quadrant = "Important, not urgent"
    elif impact == "low" and urgency == "high":
        priority = "P2"
        quadrant = "Urgent, lower impact"
    else:
        priority = "P3"
        quadrant = "Low impact, not urgent"

    return ImpactUrgencyResult(
        impact=impact,
        urgency=urgency,
        priority=priority,
        quadrant=quadrant,
        impact_reasons=impact_reasons,
        urgency_reasons=urgency_reasons,
    )


# ── Intervention type ──────────────────────────────────────────────────────────

INTERVENTION_HUMAN_LABELS = {
    "fix_driven": "Fix-driven: root cause still open",
    "price_sensitive": "Price-sensitive: billing or plan concern",
    "relationship_repair": "Relationship repair: repeated broken promises or anger",
    "firm_exit_intent": "Firm exit intent: graceful exit recommended",
    "monitor": "Monitor: low risk, no immediate action needed",
    "undetermined": "Undetermined: insufficient evidence",
}


def compute_intervention_type(
    *,
    analysis: dict[str, Any],
    risk_result: RiskResult,
    open_commitments: list[dict[str, Any]],
    turns: list[dict[str, Any]],
) -> InterventionResult:
    """
    Determine the intervention type deterministically from stored signals.
    Returns human-readable label and evidence.
    """
    customer_text = _customer_turn_texts(turns)
    evidence: list[dict[str, Any]] = []
    resolution = analysis.get("resolution", "").lower()
    reasons: list[str] = analysis.get("reasons", [])
    reasons_text = " ".join(reasons).lower()

    # Pre-compute phrase matches (used in multiple branches)
    firm_phrases = find_matching_phrases(customer_text, FIRM_EXIT_PHRASES)
    declined_phrases = find_matching_phrases(customer_text, DECLINED_OFFER_PHRASES)
    price_phrases = find_matching_phrases(customer_text, PRICE_SENSITIVE_PHRASES)
    anger_phrases = find_matching_phrases(customer_text, ANGER_PHRASES)

    cancel_comp = next(
        (c for c in risk_result.components if c.name == "cancellation_intent" and c.triggered),
        None,
    )
    broken_comp = next(
        (c for c in risk_result.components if c.name == "broken_earlier_promise" and c.triggered),
        None,
    )
    repeat_comp = next(
        (c for c in risk_result.components if c.name == "repeat_contact" and c.triggered),
        None,
    )
    billing_reason = any(
        any(bp in r.lower() for bp in BILLING_REASON_PHRASES)
        for r in reasons
    )

    has_open = len(open_commitments) > 0
    is_unresolved = resolution in ("unresolved", "pending", "partially_resolved")

    # ── 1. Firm exit intent (highest specificity) ─────────────────────────────
    # Strong phrasing + cancellation signal. Check first — even if unresolved.
    if cancel_comp and (firm_phrases or declined_phrases):
        matched = firm_phrases + declined_phrases
        evidence = [{"type": "phrase", "phrase": p} for p in matched]
        return InterventionResult(
            intervention_type="firm_exit_intent",
            matched_phrases=matched,
            evidence=evidence,
        )

    # ── 2. Price-sensitive (check before fix-driven) ──────────────────────────
    # Price language in customer text (billing_reason broadened: also check reasons text).
    price_or_retention_context = (
        billing_reason
        or any(k in reasons_text for k in ("billing", "charge", "bill", "invoice", "cancel", "churn", "retention"))
    )
    if price_phrases and price_or_retention_context:
        return InterventionResult(
            intervention_type="price_sensitive",
            matched_phrases=price_phrases,
            evidence=[{"type": "phrase", "phrase": p} for p in price_phrases[:3]],
        )

    # ── 3. Relationship repair ────────────────────────────────────────────────
    # Broken promise, OR anger phrases alone (trust issue, not just fix).
    if broken_comp or anger_phrases or (repeat_comp and len(analysis.get("reasons", [])) > 0):
        matched = anger_phrases
        ev: list[dict[str, Any]] = []
        if broken_comp:
            ev.append(broken_comp.evidence_ref)
        if anger_phrases:
            ev += [{"type": "phrase", "phrase": p} for p in anger_phrases[:2]]
        elif repeat_comp:
            ev.append({"type": "risk_component", "name": "repeat_contact"})
        return InterventionResult(
            intervention_type="relationship_repair",
            matched_phrases=matched,
            evidence=ev,
        )

    # ── 4. Fix-driven: root cause still open ─────────────────────────────────
    # Fallback for unresolved conversations not matching higher-specificity types.
    if is_unresolved or has_open:
        reasons_ev: list[dict[str, Any]] = [
            {"type": "analysis_field", "field": "resolution", "value": resolution}
        ]
        if open_commitments:
            reasons_ev.append({
                "type": "commitment",
                "count": len(open_commitments),
                "commitment_id": open_commitments[0].get("commitment_id", ""),
            })
        return InterventionResult(
            intervention_type="fix_driven",
            matched_phrases=[],
            evidence=reasons_ev,
        )

    # ── 5. Monitor (low risk, no strong signals) ──────────────────────────────
    if risk_result.risk_band == "low":
        return InterventionResult(
            intervention_type="monitor",
            matched_phrases=[],
            evidence=[{"type": "risk_band", "value": risk_result.risk_band}],
        )

    # ── 6. Undetermined ───────────────────────────────────────────────────────
    return InterventionResult(
        intervention_type="undetermined",
        matched_phrases=[],
        evidence=[],
    )



# ── What-if scenario ───────────────────────────────────────────────────────────

def compute_what_if(
    risk_result: RiskResult,
    clear_components: list[str],
) -> dict[str, Any]:
    """
    Recompute the Risk Index assuming selected components are cleared.
    clear_components: list of component names to treat as not triggered.
    Returns a dict with the scenario risk_index, risk_band, remaining components.
    """
    scenario_components = []
    for c in risk_result.components:
        if c.name in clear_components:
            scenario_components.append(
                RiskComponent(
                    name=c.name,
                    points=c.points,
                    triggered=False,
                    rule=c.rule,
                    evidence_ref=c.evidence_ref,
                    description=f"[CLEARED IN SCENARIO] {c.description}",
                )
            )
        else:
            scenario_components.append(c)

    raw = sum(c.points for c in scenario_components if c.triggered)
    idx = max(1, min(10, raw))
    band = "low" if idx <= 3 else ("medium" if idx <= 6 else "high")

    return {
        "scenario_risk_index": idx,
        "scenario_risk_band": band,
        "cleared_components": clear_components,
        "remaining_components": [
            {"name": c.name, "points": c.points, "triggered": c.triggered}
            for c in scenario_components
        ],
        "disclaimer": (
            "Scenario based on recorded signals, not a forecast of customer behavior."
        ),
    }
