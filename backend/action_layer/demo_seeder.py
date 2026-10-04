"""
backend/action_layer/demo_seeder.py
Seeds demonstration data for the Action Intelligence Layer.

Creates:
1. One ActSettings row (enabled=True, as_of_mode=dataset_max)
2. One demonstration PDCA initiative linked to the first detected recurring issue
3. Runs the full derive pipeline on all analyzed conversations

Idempotent: checks if already seeded before inserting.
Label: "DEMONSTRATION DATA — not real production records"
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.action_layer.derive_job import derive_all_pending
from backend.action_layer.issues_derive_job import derive_recurring_issues
from backend.action_layer.models import ActInitiative, ActSettings, ActRecurringIssue
from backend.models import AuditLog

logger = structlog.get_logger(__name__)

DEMO_LABEL = "DEMONSTRATION DATA — not real production records"


async def seed_demonstration(
    *,
    session: AsyncSession,
    user_id: int | None = None,
    force: bool = False,
) -> dict[str, Any]:
    """
    Seed demonstration data for the action layer.
    Idempotent — safe to call multiple times.
    Returns a summary dict.
    """
    steps: list[str] = []

    # ── Step 1: Ensure act_settings row exists and is enabled ─────────────────
    existing_settings = (await session.execute(
        select(ActSettings).limit(1)
    )).scalars().first()

    if existing_settings is None:
        settings = ActSettings(
            enabled=True,
            as_of_mode="dataset_max",
            commitment_due_soon_hours=24,
            high_impact_reasons_json=[],
        )
        session.add(settings)
        await session.flush()
        steps.append("created act_settings (enabled=True, as_of_mode=dataset_max)")
    elif not existing_settings.enabled:
        existing_settings.enabled = True
        steps.append("updated act_settings enabled=True")
    else:
        steps.append("act_settings already enabled — no change")

    # ── Step 2: Derive act_items for all analyzed conversations ───────────────
    derive_result = await derive_all_pending(session=session, limit=200, force=force)
    steps.append(
        f"derive_all_pending: derived={derive_result['derived']}, "
        f"skipped={derive_result['skipped']}, errors={derive_result['errors']}"
    )

    # ── Step 3: Derive recurring issues ───────────────────────────────────────
    issues_result = await derive_recurring_issues(session=session, force=force)
    steps.append(
        f"derive_recurring_issues: found={issues_result.get('issues_found', 0)}, "
        f"persisted={issues_result.get('issues_persisted', 0)}"
    )

    # ── Step 4: Create demonstration PDCA initiative if needed ────────────────
    existing_demo = (await session.execute(
        select(ActInitiative).where(ActInitiative.demonstration == True).limit(1)
    )).scalars().first()

    if existing_demo is None:
        # Find first recurring issue to link
        first_issue = (await session.execute(
            select(ActRecurringIssue)
            .where(ActRecurringIssue.current == True)
            .order_by(ActRecurringIssue.volume.desc())
            .limit(1)
        )).scalars().first()

        if first_issue:
            # Create a demonstration initiative at the 'check' stage
            # so the UI has something meaningful to show
            impl_date = datetime(2026, 9, 15, tzinfo=timezone.utc)
            baseline = {
                "n": first_issue.volume,
                "unresolved_rate": first_issue.unresolved_rate,
                "escalation_share": first_issue.escalation_share,
                "avg_qa_score": first_issue.avg_qa_score,
                "sentiment_mix": {},
                "window_start": str(first_issue.window_start),
                "window_end": str(first_issue.window_end),
            }
            initiative = ActInitiative(
                issue_id=first_issue.id,
                title=f"[DEMO] Reduce unresolved rate for: {first_issue.reason_label[:60]}",
                stage="check",
                iteration=1,
                demonstration=True,
                problem_statement=(
                    f"[{DEMO_LABEL}] The reason '{first_issue.reason_label}' has an "
                    f"unresolved rate of {first_issue.unresolved_rate:.0%} over "
                    f"{first_issue.volume} conversations in the analysis window."
                ),
                root_cause_hypothesis=(
                    f"[{DEMO_LABEL}] Hypothesis: agents lack a clear resolution path "
                    f"for '{first_issue.reason_label}' — needs knowledge base update. "
                    "This is a placeholder hypothesis — owner must validate."
                ),
                target_metric="unresolved_rate",
                target_change="Reduce by 20 percentage points within 30 days of implementation",
                owner="[DEMO] Contact Centre Operations",
                due_date=datetime(2026, 10, 31, tzinfo=timezone.utc),
                baseline_window_start=first_issue.window_start,
                baseline_window_end=first_issue.window_end,
                baseline_metrics_json=baseline,
                implementation_date=impl_date,
                implementation_description=(
                    f"[{DEMO_LABEL}] Updated knowledge base article for "
                    f"'{first_issue.reason_label}'. Shared with all agents via team brief."
                ),
                do_owner="[DEMO] Team Lead",
                do_status="completed",
                customers_informed=False,
                customers_informed_notes="Not applicable for internal process change.",
            )
            session.add(initiative)
            await session.flush()

            session.add(AuditLog(
                user_id=user_id,
                action="action_layer_demo_seeded",
                resource_type="act_initiative",
                resource_id=str(initiative.id),
                details_json={"demonstration": True, "label": DEMO_LABEL},
            ))

            steps.append(
                f"created demonstration initiative id={initiative.id} "
                f"for reason='{first_issue.reason_label}'"
            )
        else:
            steps.append("no recurring issues to link demonstration initiative to")
    else:
        steps.append(
            f"demonstration initiative already exists (id={existing_demo.id}) — skipped"
        )

    return {
        "status": "ok",
        "label": DEMO_LABEL,
        "steps": steps,
    }
