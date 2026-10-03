"""
backend/action_layer/agent_insights.py
Agent profile computation for the Action Intelligence Layer.

Computes per-agent metrics from stored analysis/QA/commitment data.
All metrics are described with their source field and n shown.
No fabricated metrics. If data is insufficient, says so explicitly.

Version: agent_insights_example_v1
Label: "example policy — owner review required before production use"
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

AGENT_INSIGHTS_VERSION = "agent_insights_example_v1"
AGENT_INSIGHTS_LABEL = "example policy — owner review required before production use"
AGENT_INSIGHTS_DISCLAIMER = (
    "Agent metrics are derived from automated analysis of stored conversation data. "
    "They may contain errors. Use only as one input alongside direct observation and "
    "supervisor review. Do not use as the sole basis for any employment decision."
)

MIN_CONVERSATIONS_FOR_PROFILE = 5  # below this: insufficient_data


def compute_agent_profile(
    *,
    agent_id: str,
    agent_info: dict[str, Any] | None,
    analyzed_conversations: list[dict[str, Any]],
    as_of: datetime,
) -> dict[str, Any]:
    """
    Compute an agent profile from their analyzed conversations.

    analyzed_conversations: list of merged dicts from CoreRepository.list_analyzed_conversations
    filtered to this agent.

    Returns a dict with metrics, bands, strengths, development areas, and disclaimers.
    """
    n = len(analyzed_conversations)
    agent_display = agent_id  # use ID; no PII from agent names in this view

    base = {
        "agent_id": agent_id,
        "agent_display": agent_display,
        "team_id": (agent_info or {}).get("team_id"),
        "n_conversations": n,
        "as_of": as_of.isoformat() if hasattr(as_of, "isoformat") else str(as_of),
        "rules_version": AGENT_INSIGHTS_VERSION,
        "label": AGENT_INSIGHTS_LABEL,
        "disclaimer": AGENT_INSIGHTS_DISCLAIMER,
    }

    if n < MIN_CONVERSATIONS_FOR_PROFILE:
        return {
            **base,
            "sufficient_data": False,
            "message": (
                f"Insufficient data: {n} conversation(s) available, "
                f"minimum {MIN_CONVERSATIONS_FOR_PROFILE} required for a meaningful profile."
            ),
        }

    # ── Resolution rate ────────────────────────────────────────────────────────
    resolutions = [c.get("resolution", "").lower() for c in analyzed_conversations]
    resolved_count = sum(1 for r in resolutions if r == "resolved")
    unresolved_count = sum(1 for r in resolutions if r in ("unresolved", "pending", "partially_resolved"))
    escalated_count = sum(1 for r in resolutions if r == "escalated")
    resolution_rate = resolved_count / n if n > 0 else 0.0
    unresolved_rate = unresolved_count / n if n > 0 else 0.0

    # ── QA scores ─────────────────────────────────────────────────────────────
    # QA score data is in the analysis dict if present; otherwise None
    qa_scores = [
        c.get("qa_score") for c in analyzed_conversations
        if c.get("qa_score") is not None
    ]
    avg_qa = sum(qa_scores) / len(qa_scores) if qa_scores else None
    n_with_qa = len(qa_scores)

    # ── Commitment fulfilment rate ─────────────────────────────────────────────
    total_commitments = 0
    completed_commitments = 0
    for c in analyzed_conversations:
        comms = c.get("commitments", [])
        for comm in comms:
            if not (comm.get("provisional", False)):
                total_commitments += 1
                if comm.get("status") == "completed":
                    completed_commitments += 1
    commitment_rate = (completed_commitments / total_commitments
                       if total_commitments > 0 else None)

    # ── False resolution rate ──────────────────────────────────────────────────
    false_res_count = sum(
        1 for c in analyzed_conversations if c.get("false_resolution", False)
    )
    false_resolution_rate = false_res_count / n

    # ── Churn signal rate ──────────────────────────────────────────────────────
    churn_high_count = sum(
        1 for c in analyzed_conversations if c.get("churn_risk", "").lower() == "high"
    )
    churn_signal_rate = churn_high_count / n

    # ── End-of-call sentiment distribution ────────────────────────────────────
    sentiment_counts: dict[str, int] = defaultdict(int)
    for c in analyzed_conversations:
        traj = c.get("sentiment_trajectory", [])
        if traj:
            last = traj[-1].get("sentiment", "neutral") if isinstance(traj[-1], dict) else "neutral"
            sentiment_counts[last.lower()] += 1
    positive_count = sum(
        v for k, v in sentiment_counts.items()
        if k in ("positive", "satisfied", "happy")
    )
    negative_count = sum(
        v for k, v in sentiment_counts.items()
        if k in ("negative", "frustrated", "angry", "very_negative")
    )
    positive_rate = positive_count / n
    negative_rate = negative_count / n

    # ── Common call reasons handled ────────────────────────────────────────────
    reason_counts: dict[str, int] = defaultdict(int)
    for c in analyzed_conversations:
        for reason in (c.get("reasons") or []):
            reason_counts[reason.strip()] += 1
    top_reasons = sorted(reason_counts.items(), key=lambda x: x[1], reverse=True)[:5]

    # ── QA band ───────────────────────────────────────────────────────────────
    if avg_qa is None:
        qa_band = "no_qa_data"
    elif avg_qa >= 85:
        qa_band = "strong"
    elif avg_qa >= 70:
        qa_band = "developing"
    else:
        qa_band = "needs_attention"

    # ── Resolution band ───────────────────────────────────────────────────────
    if resolution_rate >= 0.80:
        resolution_band = "strong"
    elif resolution_rate >= 0.60:
        resolution_band = "developing"
    else:
        resolution_band = "needs_attention"

    # ── Strengths / development areas ─────────────────────────────────────────
    # Based on bands — not fabricated. Each claim must reference a computed metric.
    strengths: list[str] = []
    development_areas: list[str] = []

    if resolution_band == "strong":
        strengths.append(
            f"High resolution rate ({resolution_rate:.0%}, n={n}) — issues resolved at first contact."
        )
    elif resolution_band == "needs_attention":
        development_areas.append(
            f"Resolution rate is {resolution_rate:.0%} (n={n}). "
            "Focus: root-cause questioning to resolve issues before close."
        )

    if avg_qa is not None:
        if qa_band == "strong":
            strengths.append(f"Strong QA score average ({avg_qa:.0f}/100, n={n_with_qa}).")
        elif qa_band == "needs_attention":
            development_areas.append(
                f"QA score average is {avg_qa:.0f}/100 (n={n_with_qa}). "
                "Review checklist coverage areas for coaching opportunities."
            )

    if false_resolution_rate > 0.15:
        development_areas.append(
            f"False resolution flag raised on {false_resolution_rate:.0%} of calls (n={n}). "
            "Review call closure practices."
        )

    if commitment_rate is not None and commitment_rate < 0.70:
        development_areas.append(
            f"Commitment completion rate: {commitment_rate:.0%} ({completed_commitments}/{total_commitments}). "
            "Follow-up on open commitments."
        )
    elif commitment_rate is not None and commitment_rate >= 0.90:
        strengths.append(
            f"High commitment completion rate ({commitment_rate:.0%}, {completed_commitments}/{total_commitments})."
        )

    if not strengths and not development_areas:
        strengths.append(
            f"Profile based on {n} conversations — no standout signals in either direction."
        )

    return {
        **base,
        "sufficient_data": True,
        "metrics": {
            "resolution_rate": round(resolution_rate, 3),
            "unresolved_rate": round(unresolved_rate, 3),
            "escalated_rate": round(escalated_count / n, 3),
            "false_resolution_rate": round(false_resolution_rate, 3),
            "churn_signal_rate": round(churn_signal_rate, 3),
            "positive_sentiment_rate": round(positive_rate, 3),
            "negative_sentiment_rate": round(negative_rate, 3),
            "avg_qa_score": round(avg_qa, 1) if avg_qa is not None else None,
            "n_with_qa": n_with_qa,
            "commitment_completion_rate": round(commitment_rate, 3) if commitment_rate is not None else None,
            "total_commitments": total_commitments,
            "completed_commitments": completed_commitments,
            "sentiment_distribution": dict(sentiment_counts),
            "n": n,
        },
        "bands": {
            "resolution": resolution_band,
            "qa": qa_band,
        },
        "top_call_reasons": [{"reason": r, "count": c} for r, c in top_reasons],
        "strengths": strengths,
        "development_areas": development_areas,
        "caveats": [
            f"Profile based on {n} conversations in the dataset (as-of {as_of.strftime('%Y-%m-%d') if hasattr(as_of, 'strftime') else str(as_of)}).",
            "QA scores are derived from automated phrase matching — not manual audits.",
            "These metrics are correlational, not causal. Human review is required.",
        ],
    }
