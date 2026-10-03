"""
backend/action_layer/derive_job.py
Pull-based derive job for the Action Intelligence Layer.

Rules:
- NEVER re-runs existing model analyses.
- NEVER writes to core tables.
- Only reads from core tables via CoreRepository.
- Only writes to act_* tables.
- Idempotent: re-derive creates new current rows, marks old rows current=False.
- Per-conversation lock via a simple "already has current row for this version" check.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import structlog
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.action_layer.config import (
    DEFAULT_RISK_RULES_VERSION,
    DEFAULT_PRIORITY_RULES_VERSION,
    DEFAULT_PLAYBOOK_RULES_VERSION,
    DEFAULT_PHRASE_LISTS_VERSION,
)
from backend.action_layer.draft_builder import build_template_draft
from backend.action_layer.models import ActDraft, ActItem, ActItemEvent, ActRecommendation, ActSettings
from backend.action_layer.playbook import get_recommendations
from backend.action_layer.repository import CoreRepository
from backend.action_layer.risk_engine import (
    compute_intervention_type,
    compute_priority,
    compute_risk_index,
    compute_what_if,
    INTERVENTION_HUMAN_LABELS,
)
from backend.models import AuditLog

logger = structlog.get_logger(__name__)

# Current rules bundle — all four must match for an item to be "current"
CURRENT_RULES_BUNDLE = (
    DEFAULT_RISK_RULES_VERSION,
    DEFAULT_PRIORITY_RULES_VERSION,
    DEFAULT_PLAYBOOK_RULES_VERSION,
    DEFAULT_PHRASE_LISTS_VERSION,
)


async def get_as_of(settings: ActSettings | None, repo: CoreRepository) -> datetime:
    """Resolve the as-of clock based on settings."""
    if settings is None or settings.as_of_mode == "dataset_max":
        max_dt = await repo.get_max_started_at()
        return max_dt or datetime.now(timezone.utc)
    if settings.as_of_mode == "manual" and settings.manual_as_of:
        return settings.manual_as_of
    return datetime.now(timezone.utc)


async def _get_settings(session: AsyncSession) -> ActSettings | None:
    return (await session.execute(select(ActSettings).limit(1))).scalars().first()


async def derive_single(
    *,
    conversation_id: str,
    session: AsyncSession,
    force: bool = False,
) -> dict[str, Any]:
    """
    Derive an ActItem for one conversation.

    Returns a status dict: {status, item_id, skipped_reason}
    status: "derived" | "skipped" | "error"
    """
    repo = CoreRepository(session)
    settings = await _get_settings(session)
    as_of = await get_as_of(settings, repo)
    due_soon_hours = settings.commitment_due_soon_hours if settings else 24
    high_impact_reasons = (
        settings.high_impact_reasons_json if settings else []
    ) or []

    # ── Check if already derived for current rules bundle ────────────────────
    if not force:
        existing = (await session.execute(
            select(ActItem)
            .where(
                ActItem.conversation_id == conversation_id,
                ActItem.current == True,
                ActItem.risk_rules_version == DEFAULT_RISK_RULES_VERSION,
                ActItem.priority_rules_version == DEFAULT_PRIORITY_RULES_VERSION,
                ActItem.playbook_rules_version == DEFAULT_PLAYBOOK_RULES_VERSION,
                ActItem.phrase_lists_version == DEFAULT_PHRASE_LISTS_VERSION,
            )
        )).scalars().first()
        if existing:
            return {"status": "skipped", "item_id": existing.id,
                    "skipped_reason": "already_derived_for_current_rules"}

    # ── Fetch all inputs from core tables (read-only) ─────────────────────────
    analysis = await repo.get_final_analysis(conversation_id)
    if analysis is None:
        return {"status": "skipped", "item_id": None,
                "skipped_reason": "no_final_analysis"}

    conversation = await repo.get_conversation(conversation_id)
    if conversation is None:
        return {"status": "skipped", "item_id": None,
                "skipped_reason": "conversation_not_found"}

    commitments = await repo.get_commitments(conversation_id)
    open_commitments = [
        c for c in commitments
        if c.get("status") not in ("completed", "cancelled")
    ]
    qa_result = await repo.get_qa_result(conversation_id)
    turns = await repo.get_turns(conversation_id)
    cases = await repo.get_cases_for_conversation(conversation_id)

    # Gather commitments from other conversations in linked cases
    case_other_commitments: list[dict[str, Any]] = []
    for case in cases:
        case_conv_ids = await repo.get_conversations_in_case(case["case_id"])
        for cid in case_conv_ids:
            if cid != conversation_id:
                case_other_commitments += await repo.get_commitments(cid)

    # ── Compute Risk Index ────────────────────────────────────────────────────
    risk_result = compute_risk_index(
        analysis=analysis,
        commitments=commitments,
        qa_result=qa_result,
        turns=turns,
        cases=cases,
        case_other_commitments=case_other_commitments,
        as_of=as_of,
        due_soon_hours=due_soon_hours,
    )

    # ── Compute Priority ──────────────────────────────────────────────────────
    priority_result = compute_priority(
        risk_result=risk_result,
        analysis=analysis,
        open_commitments=open_commitments,
        turns=turns,
        cases=cases,
        high_impact_reasons=high_impact_reasons or None,
        due_soon_hours=due_soon_hours,
    )

    # ── Compute Intervention type ─────────────────────────────────────────────
    intervention_result = compute_intervention_type(
        analysis=analysis,
        risk_result=risk_result,
        open_commitments=open_commitments,
        turns=turns,
    )

    # ── Determine data_source ────────────────────────────────────────────────
    data_source = "live" if conversation.get("source_id") is None else "dataset_pool"

    # ── Mark old items non-current ────────────────────────────────────────────
    await session.execute(
        update(ActItem)
        .where(ActItem.conversation_id == conversation_id, ActItem.current == True)
        .values(current=False)
    )

    # ── Create the new ActItem ────────────────────────────────────────────────
    risk_components_json = [
        {
            "name": c.name,
            "points": c.points,
            "triggered": c.triggered,
            "rule": c.rule,
            "evidence_ref": c.evidence_ref,
            "description": c.description,
        }
        for c in risk_result.components
    ]

    item = ActItem(
        conversation_id=conversation_id,
        analysis_version=analysis["version"],
        risk_rules_version=DEFAULT_RISK_RULES_VERSION,
        priority_rules_version=DEFAULT_PRIORITY_RULES_VERSION,
        playbook_rules_version=DEFAULT_PLAYBOOK_RULES_VERSION,
        phrase_lists_version=DEFAULT_PHRASE_LISTS_VERSION,
        risk_index=risk_result.risk_index,
        risk_band=risk_result.risk_band,
        risk_components_json=risk_components_json,
        impact=priority_result.impact,
        urgency=priority_result.urgency,
        priority=priority_result.priority,
        quadrant=priority_result.quadrant,
        intervention_type=intervention_result.intervention_type,
        intervention_evidence_json=intervention_result.evidence,
        evidence_complete=risk_result.evidence_complete,
        evidence_incomplete_reasons_json=risk_result.evidence_incomplete_reasons,
        data_source=data_source,
        status="new",
        current=True,
    )
    session.add(item)
    await session.flush()  # get item.id

    # ── Create recommendations ────────────────────────────────────────────────
    recommendations = get_recommendations(
        intervention_type=intervention_result.intervention_type,
        intervention_evidence=intervention_result.evidence,
        risk_result_components=risk_result.components,
    )
    for rec in recommendations:
        r = ActRecommendation(
            item_id=item.id,
            rank=rec["rank"],
            action_key=rec["action_key"],
            title=rec["title"],
            justification=rec["justification"],
            signal_refs_json=rec["signal_refs"],
            playbook_rule_id=rec["playbook_rule_id"],
            constraint_note=rec["constraint_note"],
        )
        session.add(r)

    # ── Create template draft ─────────────────────────────────────────────────
    draft_data = build_template_draft(
        analysis=analysis,
        open_commitments=open_commitments,
        intervention_type=intervention_result.intervention_type,
        conversation_id=conversation_id,
    )
    draft = ActDraft(
        item_id=item.id,
        kind="template",
        content=draft_data["content"],
        facts_used_json=draft_data["facts_used"],
        placeholders_json=draft_data["placeholders"],
        gate_status=draft_data["gate_status"],
    )
    session.add(draft)

    # ── Create derive event ────────────────────────────────────────────────────
    event = ActItemEvent(
        item_id=item.id,
        event_type="derived",
        from_status=None,
        to_status="new",
        actor_user_id=None,
        notes=(
            f"Derived by action layer derive job. "
            f"Rules: risk={DEFAULT_RISK_RULES_VERSION}, "
            f"priority={DEFAULT_PRIORITY_RULES_VERSION}, "
            f"playbook={DEFAULT_PLAYBOOK_RULES_VERSION}."
        ),
    )
    session.add(event)

    # ── Audit log entry ───────────────────────────────────────────────────────
    audit = AuditLog(
        user_id=None,
        action="action_layer_derive",
        resource_type="act_item",
        resource_id=str(item.id),
        details_json={
            "conversation_id": conversation_id,
            "risk_index": risk_result.risk_index,
            "priority": priority_result.priority,
            "intervention_type": intervention_result.intervention_type,
            "rules_bundle": list(CURRENT_RULES_BUNDLE),
        },
    )
    session.add(audit)

    await session.flush()

    logger.info(
        "action_layer.derived",
        conversation_id=conversation_id,
        item_id=item.id,
        risk_index=risk_result.risk_index,
        priority=priority_result.priority,
        intervention_type=intervention_result.intervention_type,
    )

    return {
        "status": "derived",
        "item_id": item.id,
        "risk_index": risk_result.risk_index,
        "risk_band": risk_result.risk_band,
        "priority": priority_result.priority,
        "intervention_type": intervention_result.intervention_type,
    }


async def derive_all_pending(
    *,
    session: AsyncSession,
    limit: int = 200,
    force: bool = False,
) -> dict[str, Any]:
    """
    Find all conversations with a final analysis but no current act_item
    for the current rules bundle, and derive items for them.
    Returns a summary dict.
    """
    from backend.models import Analysis, Conversation

    # Find conversations with final analyses
    analyzed_rows = (await session.execute(
        select(Analysis.conversation_id, Analysis.version)
        .where(Analysis.provisional == False)
        .distinct(Analysis.conversation_id)
        .limit(limit)
    )).fetchall()

    if not analyzed_rows:
        return {"status": "ok", "derived": 0, "skipped": 0, "errors": 0, "total": 0}

    derived = skipped = errors = 0
    details: list[dict[str, Any]] = []

    for conv_id, _version in analyzed_rows:
        try:
            result = await derive_single(
                conversation_id=conv_id,
                session=session,
                force=force,
            )
            if result["status"] == "derived":
                derived += 1
            else:
                skipped += 1
            details.append(result)
        except Exception as e:
            errors += 1
            logger.exception("action_layer.derive_error", conversation_id=conv_id, error=str(e))
            details.append({"status": "error", "conversation_id": conv_id, "error": str(e)})

    return {
        "status": "ok",
        "derived": derived,
        "skipped": skipped,
        "errors": errors,
        "total": len(analyzed_rows),
        "details": details,
    }
