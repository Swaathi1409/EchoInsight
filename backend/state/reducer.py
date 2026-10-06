"""
Idempotent state reducer. Applies per-turn extraction results to build
provisional state. Append-only: writes StateEvent rows, derives current
state by replaying them.
"""
from __future__ import annotations

import uuid
from datetime import UTC, datetime

from backend.domain_model import ChurnRisk, CommitmentStatus, CustomerSentiment, ResolutionStatus


def _sentinel_sentiment(signals: list[str]) -> ChurnRisk:
    """Derive churn risk from ordered churn signal list."""
    if not signals:
        return ChurnRisk.LOW
    last = signals[-1]
    if last == "high":
        return ChurnRisk.HIGH
    if last == "medium":
        return ChurnRisk.MEDIUM
    return ChurnRisk.LOW


def apply_turn_extraction(
    existing_state: dict,
    extraction: dict,
    turn_id: str,
    turn_text: str,
) -> dict:
    """
    Merge per-turn extraction result into the running state dict.
    Returns new state dict (immutable merge).
    """
    state = dict(existing_state)

    # Resolution
    res = extraction.get("resolution_update", "no_change")
    if res != "no_change":
        state["resolution"] = res

    # Sentiment
    sent = extraction.get("sentiment")
    if sent:
        trajectory = list(state.get("sentiment_trajectory", []))
        trajectory.append({"turn_id": turn_id, "sentiment": sent})
        state["sentiment_trajectory"] = trajectory
        state["sentiment_current"] = sent

    # Churn signal
    churn_signal = extraction.get("churn_signal", "none")
    if churn_signal != "none":
        signals = list(state.get("churn_signals", []))
        signals.append(churn_signal)
        state["churn_signals"] = signals
        state["churn_risk"] = _sentinel_sentiment(signals).value

    # New commitments
    commitments = list(state.get("commitments", []))
    for c in extraction.get("new_commitments", []):
        commitments.append({
            "commitment_id": str(uuid.uuid4()),
            "description": c.get("description", ""),
            "owner": c.get("owner", ""),
            "deadline": c.get("deadline", ""),
            "deadline_flag": c.get("deadline_flag", ""),
            "status": CommitmentStatus.PROPOSED.value,
            "provisional": True,
            "created_at_turn_id": turn_id,
            "completed_at_turn_id": None,
            "carried_over": False,
            "evidence": [{"turn_id": c.get("turn_id", turn_id), "quote": c.get("quote", "")}],
        })

    # Completed commitments
    completed_ids = extraction.get("completed_commitments", [])
    for i, c in enumerate(commitments):
        if c.get("commitment_id") in completed_ids or c.get("description") in completed_ids:
            commitments[i] = {**c, "status": CommitmentStatus.COMPLETED.value,
                              "completed_at_turn_id": turn_id}

    state["commitments"] = commitments
    state["open_commitments"] = [c for c in commitments if c.get("status") not in ("completed", "cancelled")]
    state["as_of_turn_id"] = turn_id
    state["updated_at"] = datetime.now(UTC).isoformat()
    return state


def initial_state(conversation_id: str) -> dict:
    return {
        "conversation_id": conversation_id,
        "provisional": True,
        "as_of_turn_id": "",
        "reasons": [],
        "resolution": ResolutionStatus.UNKNOWN.value,
        "sentiment_current": CustomerSentiment.NEUTRAL.value,
        "sentiment_trajectory": [],
        "churn_risk": ChurnRisk.LOW.value,
        "churn_signals": [],
        "commitments": [],
        "open_commitments": [],
        "updated_at": datetime.now(UTC).isoformat(),
    }
