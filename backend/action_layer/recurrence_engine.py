"""
backend/action_layer/recurrence_engine.py
Deterministic recurring issue detection.

Per call-reason label: computes volume, trend, unresolved rate, escalation share,
QA gaps, repeat-customer share, and example quotes. Flags an issue as recurring
when it exceeds configured thresholds.

Version: recurrence_example_v1
Label: "example policy — owner review required before production use"

SAFETY:
- Reads only from core tables via CoreRepository.
- Never writes to core tables.
- All findings reference verifiable stored data (n shown).
"""
from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

import structlog

from backend.action_layer.config import PDCA_MIN_POST_CONVERSATIONS, PDCA_MIN_POST_DAYS

logger = structlog.get_logger(__name__)

RECURRENCE_RULES_VERSION = "recurrence_example_v1"
RECURRENCE_RULES_LABEL = "example policy — owner review required before production use"

# ── Default thresholds (versioned, configurable) ──────────────────────────────
DEFAULT_MIN_VOLUME = 3             # minimum conversations in window to flag
DEFAULT_MIN_UNRESOLVED_RATE = 0.4  # 40%+ unresolved rate
DEFAULT_MIN_TREND_PCT = 0.20       # 20%+ increase in current vs previous window
DEFAULT_MIN_ESCALATION_SHARE = 0.3 # 30%+ escalation rate


def _window_split(
    conversations: list[dict[str, Any]],
    as_of: datetime,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], datetime, datetime]:
    """
    Split conversations into current and previous windows.
    Auto-granularity: if data spans > 14 days, use 7-day windows; else split in half.
    Returns (current_window, prev_window, window_start, window_end).
    """
    if not conversations:
        return [], [], as_of, as_of

    dates = [
        c["conversation"]["started_at"]
        for c in conversations
        if c.get("conversation", {}).get("started_at")
    ]
    if not dates:
        return conversations, [], as_of, as_of

    min_date = min(dates)
    max_date = max(dates)
    if hasattr(min_date, "replace"):
        min_date = min_date.replace(tzinfo=timezone.utc) if min_date.tzinfo is None else min_date
    if hasattr(max_date, "replace"):
        max_date = max_date.replace(tzinfo=timezone.utc) if max_date.tzinfo is None else max_date

    span_days = max(1, (max_date - min_date).days)

    if span_days >= 14:
        window_days = 7
        cutoff = datetime(
            max_date.year, max_date.month, max_date.day, tzinfo=timezone.utc
        )
        from datetime import timedelta
        cutoff -= timedelta(days=window_days)
    else:
        # Split in half
        midpoint = min_date + (max_date - min_date) / 2
        cutoff = midpoint

    current = []
    prev = []
    for c in conversations:
        started = c.get("conversation", {}).get("started_at")
        if started is None:
            current.append(c)
            continue
        if hasattr(started, "replace") and started.tzinfo is None:
            started = started.replace(tzinfo=timezone.utc)
        if started >= cutoff:
            current.append(c)
        else:
            prev.append(c)

    return current, prev, cutoff, max_date


def _is_unresolved(resolution: str) -> bool:
    return resolution.lower() in ("unresolved", "pending", "partially_resolved")


def _extract_quotes(
    conversations: list[dict[str, Any]],
    reason_label: str,
    max_quotes: int = 3,
) -> list[dict[str, Any]]:
    """
    Extract example customer turn quotes from conversations matching this reason.
    Returns list of {conv_id, turn_id, quote}.
    Only includes turns with meaningful length (>20 chars).
    """
    quotes = []
    for c in conversations[:10]:  # search first 10 only for efficiency
        turns = c.get("turns", [])
        for turn in turns:
            if turn.get("speaker", "").lower() in ("customer", "user", "caller"):
                text = turn.get("text_redacted", "")
                if len(text) > 20:
                    quotes.append({
                        "conv_id": c["conversation"]["id"],
                        "turn_id": turn.get("turn_id", ""),
                        "quote": text[:200],  # truncate for storage
                    })
                    if len(quotes) >= max_quotes:
                        return quotes
    return quotes


def detect_recurring_issues(
    *,
    analyzed_conversations: list[dict[str, Any]],
    conversations_with_turns: dict[str, list[dict[str, Any]]],  # conv_id → turns
    as_of: datetime,
    min_volume: int = DEFAULT_MIN_VOLUME,
    min_unresolved_rate: float = DEFAULT_MIN_UNRESOLVED_RATE,
    min_trend_pct: float = DEFAULT_MIN_TREND_PCT,
    min_escalation_share: float = DEFAULT_MIN_ESCALATION_SHARE,
) -> list[dict[str, Any]]:
    """
    Detect recurring issues from analyzed conversations.
    Returns a list of issue dicts, one per flagged reason label.
    """
    # Group conversations by their call reason labels
    reason_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for conv_data in analyzed_conversations:
        reasons: list[str] = conv_data.get("reasons", [])
        # Attach turns for quote extraction
        conv_id = conv_data.get("conversation_id", "")
        turns = conversations_with_turns.get(conv_id, [])
        conv_data_with_turns = {**conv_data, "turns": turns}
        for reason in reasons:
            reason_groups[reason.strip()].append(conv_data_with_turns)

    issues = []
    for reason_label, convs in reason_groups.items():
        if len(convs) < min_volume:
            continue

        current_window, prev_window, window_start, window_end = _window_split(convs, as_of)

        if len(current_window) < min_volume:
            continue

        # Compute metrics for current window
        n_current = len(current_window)
        n_prev = len(prev_window)
        n_unresolved = sum(
            1 for c in current_window if _is_unresolved(c.get("resolution", ""))
        )
        n_escalated = sum(
            1 for c in current_window if c.get("resolution", "").lower() == "escalated"
        )

        unresolved_rate = n_unresolved / n_current if n_current > 0 else 0.0
        escalation_share = n_escalated / n_current if n_current > 0 else 0.0

        # Trend
        if n_prev >= 1:
            trend_pct = (n_current - n_prev) / n_prev
            if trend_pct > 0.01:
                trend_direction = "up"
            elif trend_pct < -0.01:
                trend_direction = "down"
            else:
                trend_direction = "flat"
        else:
            trend_pct = None
            trend_direction = "insufficient_data"

        # QA gaps: average QA score for this reason
        qa_scores = [
            c.get("qa_score") for c in current_window if c.get("qa_score") is not None
        ]
        avg_qa = sum(qa_scores) / len(qa_scores) if qa_scores else None

        # Repeat contact share: conversations in a linked case
        # (simplified: if case_id is present on conversation record)
        repeat_count = sum(
            1 for c in current_window
            if c.get("conversation", {}).get("case_id") is not None
        )
        repeat_contact_share = repeat_count / n_current if n_current > 0 else 0.0

        # Example quotes from customer turns
        quotes = _extract_quotes(current_window, reason_label)

        # Determine which thresholds fired
        triggered = []
        if unresolved_rate >= min_unresolved_rate:
            triggered.append(
                f"unresolved_rate {unresolved_rate:.0%} >= threshold {min_unresolved_rate:.0%}"
            )
        if trend_direction == "up" and trend_pct is not None and trend_pct >= min_trend_pct:
            triggered.append(
                f"trend up {trend_pct:.0%} >= threshold {min_trend_pct:.0%}"
            )
        if escalation_share >= min_escalation_share:
            triggered.append(
                f"escalation_share {escalation_share:.0%} >= threshold {min_escalation_share:.0%}"
            )

        if not triggered:
            continue  # didn't exceed any threshold

        issues.append({
            "reason_label": reason_label,
            "rules_version": RECURRENCE_RULES_VERSION,
            "label": RECURRENCE_RULES_LABEL,
            "window_start": window_start,
            "window_end": window_end,
            "volume": n_current,
            "prev_window_volume": n_prev if n_prev > 0 else None,
            "unresolved_rate": round(unresolved_rate, 3),
            "escalation_share": round(escalation_share, 3),
            "trend_direction": trend_direction,
            "trend_pct_change": round(trend_pct, 3) if trend_pct is not None else None,
            "avg_qa_score": round(avg_qa, 1) if avg_qa is not None else None,
            "repeat_contact_share": round(repeat_contact_share, 3),
            "example_quotes": quotes,
            "triggered_thresholds": triggered,
            "n": n_current,
            "thresholds_used": {
                "min_volume": min_volume,
                "min_unresolved_rate": min_unresolved_rate,
                "min_trend_pct": min_trend_pct,
                "min_escalation_share": min_escalation_share,
            },
        })

    return sorted(issues, key=lambda x: x["volume"], reverse=True)


def compute_pdca_check(
    *,
    baseline_metrics: dict[str, Any],
    post_conversations: list[dict[str, Any]],
    reason_label: str,
    implementation_date: datetime,
    as_of: datetime,
    min_post_days: int = PDCA_MIN_POST_DAYS,
    min_post_conversations: int = PDCA_MIN_POST_CONVERSATIONS,
) -> dict[str, Any]:
    """
    Compute the PDCA Check phase automatically.
    Compares post-implementation metrics against the frozen baseline.

    Returns:
        {sufficient_data, post_n, post_metrics, check_results, caveats}
    """
    from datetime import timedelta

    post_convs = [
        c for c in post_conversations
        if c.get("conversation", {}).get("started_at") is not None
        and (lambda s: (
            s.replace(tzinfo=timezone.utc) if s.tzinfo is None else s
        ) >= (
            implementation_date.replace(tzinfo=timezone.utc)
            if implementation_date.tzinfo is None else implementation_date
        ))(c["conversation"]["started_at"])
    ]

    n_post = len(post_convs)
    days_since = (
        (as_of.replace(tzinfo=timezone.utc) if as_of.tzinfo is None else as_of)
        - (implementation_date.replace(tzinfo=timezone.utc)
           if implementation_date.tzinfo is None else implementation_date)
    ).days

    if n_post < min_post_conversations or days_since < min_post_days:
        return {
            "sufficient_data": False,
            "post_n": n_post,
            "days_since_implementation": days_since,
            "min_post_conversations": min_post_conversations,
            "min_post_days": min_post_days,
            "message": (
                f"Not enough post-fix data yet "
                f"({n_post} of {min_post_conversations} conversations, "
                f"{days_since} of {min_post_days} days required)."
            ),
            "check_results": {},
        }

    # Compute post metrics
    n_unresolved_post = sum(
        1 for c in post_convs if _is_unresolved(c.get("resolution", ""))
    )
    post_unresolved_rate = n_unresolved_post / n_post if n_post > 0 else 0.0

    # End-of-call sentiment
    sentiment_counts: dict[str, int] = defaultdict(int)
    for c in post_convs:
        traj = c.get("sentiment_trajectory", [])
        if traj:
            last = traj[-1].get("sentiment", "neutral")
            sentiment_counts[last.lower()] += 1

    # QA score
    qa_scores = [
        c.get("qa_score") for c in post_convs if c.get("qa_score") is not None
    ]
    post_avg_qa = sum(qa_scores) / len(qa_scores) if qa_scores else None

    # Build check results comparing against frozen baseline
    baseline_unresolved_rate = baseline_metrics.get("unresolved_rate", 0.0)
    baseline_n = baseline_metrics.get("n", 0)

    check_results: dict[str, Any] = {}

    # Unresolved rate comparison
    if baseline_n > 0:
        rate_change = post_unresolved_rate - baseline_unresolved_rate
        rate_change_pct = (rate_change / baseline_unresolved_rate * 100
                           if baseline_unresolved_rate > 0 else None)
        check_results["unresolved_rate"] = {
            "metric": "Unresolved rate",
            "baseline_value": round(baseline_unresolved_rate, 3),
            "post_value": round(post_unresolved_rate, 3),
            "change_abs": round(rate_change, 3),
            "change_pct": round(rate_change_pct, 1) if rate_change_pct is not None else None,
            "n_baseline": baseline_n,
            "n_post": n_post,
            "direction": "improved" if rate_change < -0.02 else (
                "worsened" if rate_change > 0.02 else "no_clear_change"
            ),
        }

    # Sentiment mix
    check_results["sentiment_mix"] = {
        "metric": "End-of-call sentiment distribution",
        "post_n": n_post,
        "post_counts": dict(sentiment_counts),
        "baseline_sentiment_mix": baseline_metrics.get("sentiment_mix", {}),
    }

    # QA score
    if post_avg_qa is not None:
        baseline_qa = baseline_metrics.get("avg_qa_score")
        check_results["avg_qa_score"] = {
            "metric": "Average QA score",
            "baseline_value": round(baseline_qa, 1) if baseline_qa else None,
            "post_value": round(post_avg_qa, 1),
            "n_post": len(qa_scores),
        }

    return {
        "sufficient_data": True,
        "post_n": n_post,
        "days_since_implementation": days_since,
        "check_results": check_results,
        "caveats": (
            "Indicative only: other factors may have changed during this period; "
            "this is a correlation, not proof of causation. Sample sizes are small."
        ),
    }
