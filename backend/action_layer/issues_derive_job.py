"""
backend/action_layer/issues_derive_job.py
Pull-based derive job for recurring issues, prevention suggestions, and PDCA check updates.

Rules:
- Reads core tables only via CoreRepository.
- Only writes to act_recurring_issues, act_prevention_suggestions, act_initiatives (check fields).
- Idempotent: marks old current=True rows current=False before inserting new ones.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.action_layer.derive_job import get_as_of, _get_settings
from backend.action_layer.models import (
    ActInitiative, ActPreventionSuggestion, ActRecurringIssue,
)
from backend.action_layer.prevention_library import get_prevention_suggestions
from backend.action_layer.recurrence_engine import (
    RECURRENCE_RULES_VERSION,
    compute_pdca_check,
    detect_recurring_issues,
)
from backend.action_layer.repository import CoreRepository
from backend.models import AuditLog

logger = structlog.get_logger(__name__)


async def derive_recurring_issues(
    *,
    session: AsyncSession,
    force: bool = False,
) -> dict[str, Any]:
    """
    Detect recurring issues from all analyzed conversations and persist them.
    Returns a summary dict.
    """
    repo = CoreRepository(session)
    settings = await _get_settings(session)
    as_of = await get_as_of(settings, repo)

    # Fetch all analyzed conversations
    analyzed_convs = await repo.list_analyzed_conversations(limit=500)
    if not analyzed_convs:
        return {"status": "ok", "issues_found": 0, "message": "no analyzed conversations"}

    # Fetch turns for each conversation (for quote extraction)
    conv_turns: dict[str, list[dict[str, Any]]] = {}
    for conv_data in analyzed_convs:
        conv_id = conv_data.get("conversation_id", "")
        if conv_id:
            conv_turns[conv_id] = await repo.get_turns(conv_id)

    # Detect issues
    issues = detect_recurring_issues(
        analyzed_conversations=analyzed_convs,
        conversations_with_turns=conv_turns,
        as_of=as_of,
    )

    if not issues:
        return {"status": "ok", "issues_found": 0, "message": "no issues detected"}

    persisted = 0
    for issue_data in issues:
        reason_label = issue_data["reason_label"]

        # Mark old current rows non-current
        await session.execute(
            update(ActRecurringIssue)
            .where(
                ActRecurringIssue.reason_label == reason_label,
                ActRecurringIssue.current == True,
            )
            .values(current=False)
        )

        # Persist new current row
        issue_row = ActRecurringIssue(
            reason_label=reason_label,
            rules_version=RECURRENCE_RULES_VERSION,
            window_start=issue_data.get("window_start"),
            window_end=issue_data.get("window_end"),
            volume=issue_data["volume"],
            unresolved_rate=issue_data["unresolved_rate"],
            trend_direction=issue_data["trend_direction"],
            trend_pct_change=issue_data.get("trend_pct_change"),
            prev_window_volume=issue_data.get("prev_window_volume"),
            escalation_share=issue_data.get("escalation_share", 0.0),
            avg_qa_score=issue_data.get("avg_qa_score"),
            repeat_contact_share=issue_data.get("repeat_contact_share", 0.0),
            example_quotes_json=issue_data.get("example_quotes", []),
            triggered_thresholds_json=issue_data.get("triggered_thresholds", []),
            current=True,
        )
        session.add(issue_row)
        await session.flush()

        # Persist prevention suggestions for this issue
        suggestions = get_prevention_suggestions(issue_data)
        for suggestion in suggestions:
            s_row = ActPreventionSuggestion(
                issue_id=issue_row.id,
                rules_version=suggestion["rules_version"],
                suggestion_text=suggestion["suggestion_text"],
                suggested_owner=suggestion["suggested_owner"],
                prevention_rule_id=suggestion["prevention_rule_id"],
                evidence_json=suggestion["evidence"],
            )
            session.add(s_row)

        # Audit
        session.add(AuditLog(
            user_id=None,
            action="action_layer_recurring_issue_derived",
            resource_type="act_recurring_issue",
            resource_id=str(issue_row.id),
            details_json={
                "reason_label": reason_label,
                "volume": issue_data["volume"],
                "unresolved_rate": issue_data["unresolved_rate"],
                "trend_direction": issue_data["trend_direction"],
                "rules_version": RECURRENCE_RULES_VERSION,
            },
        ))

        persisted += 1
        logger.info(
            "action_layer.recurring_issue_derived",
            reason_label=reason_label,
            volume=issue_data["volume"],
            triggered=issue_data.get("triggered_thresholds", []),
        )

    return {
        "status": "ok",
        "issues_found": len(issues),
        "issues_persisted": persisted,
    }


async def run_pdca_check_updates(
    *,
    session: AsyncSession,
) -> dict[str, Any]:
    """
    For all PDCA initiatives in the 'check' stage or 'do' stage with an implementation_date,
    recompute the Check metrics against post-implementation data.
    """
    repo = CoreRepository(session)
    settings = await _get_settings(session)
    as_of = await get_as_of(settings, repo)

    # Find initiatives that have moved to do stage with an implementation date
    initiatives = (await session.execute(
        select(ActInitiative)
        .where(
            ActInitiative.stage.in_(["do", "check", "act"]),
            ActInitiative.implementation_date.isnot(None),
        )
    )).scalars().all()

    if not initiatives:
        return {"status": "ok", "updated": 0, "message": "no initiatives eligible for check"}

    updated = 0
    for initiative in initiatives:
        if initiative.issue_id is None:
            continue

        # Get the linked recurring issue for the reason label
        issue_row = (await session.execute(
            select(ActRecurringIssue)
            .where(ActRecurringIssue.id == initiative.issue_id)
        )).scalars().first()
        if issue_row is None:
            continue

        # Get all analyzed conversations for this reason label
        all_convs = await repo.list_analyzed_conversations(limit=500)
        post_convs = [
            c for c in all_convs
            if issue_row.reason_label in (c.get("reasons") or [])
        ]

        baseline_metrics = initiative.baseline_metrics_json or {}
        check_result = compute_pdca_check(
            baseline_metrics=baseline_metrics,
            post_conversations=post_convs,
            reason_label=issue_row.reason_label,
            implementation_date=initiative.implementation_date,
            as_of=as_of,
        )

        initiative.check_computed_at = as_of
        initiative.check_post_n = check_result.get("post_n", 0)
        initiative.check_sufficient_data = check_result.get("sufficient_data", False)
        initiative.check_results_json = check_result

        if check_result.get("sufficient_data"):
            # Find the post window times
            post_dates = [
                c["conversation"]["started_at"] for c in post_convs
                if c.get("conversation", {}).get("started_at") is not None
                and c["conversation"]["started_at"] >= initiative.implementation_date
            ]
            if post_dates:
                initiative.check_post_window_start = min(post_dates)
                initiative.check_post_window_end = max(post_dates)
            updated += 1

    return {"status": "ok", "updated": updated, "total": len(initiatives)}
