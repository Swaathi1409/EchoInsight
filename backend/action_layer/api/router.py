"""
backend/action_layer/api/router.py
Full action layer API router.

Endpoints:
  GET  /api/v1/action/status
  GET  /api/v1/action/settings
  POST /api/v1/action/settings
  POST /api/v1/action/seed-demo          (admin only)
  POST /api/v1/action/derive             (admin only)
  POST /api/v1/action/derive-issues      (admin only)
  GET  /api/v1/action/items              ?priority=P1&status=new&limit=50&offset=0
  GET  /api/v1/action/items/{item_id}
  POST /api/v1/action/items/{item_id}/transition
  GET  /api/v1/action/items/{item_id}/draft
  GET  /api/v1/action/items/{item_id}/what-if
  GET  /api/v1/action/issues
  GET  /api/v1/action/issues/{issue_id}
  GET  /api/v1/action/initiatives
  GET  /api/v1/action/initiatives/{initiative_id}
  POST /api/v1/action/initiatives
  PUT  /api/v1/action/initiatives/{initiative_id}
  GET  /api/v1/action/agents/{agent_id}/profile

All endpoints:
- Check master switch first; return {"enabled": false} if off.
- Never read from core tables directly; go through CoreRepository.
- Audit every write.
"""
from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.action_layer.guard import is_action_layer_enabled, disabled_response
from backend.action_layer.models import (
    ActDraft, ActInitiative, ActInitiativeEvent, ActItem, ActRecommendation,
    ActRecurringIssue, ActSettings, ActPreventionSuggestion,
)
from backend.action_layer.repository import CoreRepository
from backend.action_layer.risk_engine import compute_what_if, RiskComponent, RiskResult
from backend.action_layer.workflow import transition_item, WorkflowError
from backend.api.deps import get_current_user
from backend.db import _db_session_dependency
from backend.models import AuditLog

router = APIRouter(prefix="/action", tags=["action-layer"])


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class TransitionRequest(BaseModel):
    to_status: str
    notes: str = ""
    outcome: str | None = None
    dismissal_reason: str | None = None


class SettingsUpdate(BaseModel):
    enabled: bool | None = None
    as_of_mode: str | None = None
    commitment_due_soon_hours: int | None = None
    high_impact_reasons_json: list[str] | None = None


class InitiativeCreate(BaseModel):
    issue_id: int | None = None
    title: str
    problem_statement: str = ""
    root_cause_hypothesis: str = ""
    metric_key: str = ""          # e.g. "unresolved_rate" | "weekly_volume" | "escalation_rate"
    target_value: float | None = None  # numeric target
    # legacy free-text kept for backward compat
    target_metric: str = ""
    target_change: str = ""
    owner: str = ""
    due_date: str | None = None


class InitiativeUpdate(BaseModel):
    stage: str | None = None
    # PLAN updates
    problem_statement: str | None = None
    root_cause_hypothesis: str | None = None
    metric_key: str | None = None
    target_value: float | None = None
    owner: str | None = None
    due_date: str | None = None
    # DO updates
    implementation_date: str | None = None
    implementation_description: str | None = None
    do_owner: str | None = None
    do_status: str | None = None
    customers_informed: bool | None = None
    customers_informed_notes: str | None = None
    # ACT updates
    act_decision: str | None = None
    act_notes: str | None = None
    notes: str = ""


class WhatIfRequest(BaseModel):
    clear_components: list[str] = Field(default_factory=list)


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _get_settings_row(session: AsyncSession) -> ActSettings | None:
    return (await session.execute(select(ActSettings).limit(1))).scalars().first()


def _item_to_dict(item: ActItem) -> dict[str, Any]:
    return {
        "id": item.id,
        "conversation_id": item.conversation_id,
        "analysis_version": item.analysis_version,
        "risk_index": item.risk_index,
        "risk_band": item.risk_band,
        "impact": item.impact,
        "urgency": item.urgency,
        "priority": item.priority,
        "quadrant": item.quadrant,
        "intervention_type": item.intervention_type,
        "intervention_evidence": item.intervention_evidence_json,
        "evidence_complete": item.evidence_complete,
        "evidence_incomplete_reasons": item.evidence_incomplete_reasons_json,
        "status": item.status,
        "assignee_user_id": item.assignee_user_id,
        "data_source": item.data_source,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


def _issue_to_dict(issue: ActRecurringIssue) -> dict[str, Any]:
    return {
        "id": issue.id,
        "reason_label": issue.reason_label,
        "rules_version": issue.rules_version,
        "window_start": issue.window_start.isoformat() if issue.window_start else None,
        "window_end": issue.window_end.isoformat() if issue.window_end else None,
        "volume": issue.volume,
        "unresolved_rate": issue.unresolved_rate,
        "trend_direction": issue.trend_direction,
        "trend_pct_change": issue.trend_pct_change,
        "prev_window_volume": issue.prev_window_volume,
        "escalation_share": issue.escalation_share,
        "avg_qa_score": issue.avg_qa_score,
        "repeat_contact_share": issue.repeat_contact_share,
        "example_quotes": issue.example_quotes_json,
        "triggered_thresholds": issue.triggered_thresholds_json,
        "created_at": issue.created_at.isoformat() if issue.created_at else None,
    }


def _initiative_to_dict(ini: ActInitiative) -> dict[str, Any]:
    return {
        "id": ini.id,
        "issue_id": ini.issue_id,
        "title": ini.title,
        "stage": ini.stage,
        "iteration": ini.iteration,
        "demonstration": ini.demonstration,
        "problem_statement": ini.problem_statement,
        "root_cause_hypothesis": ini.root_cause_hypothesis,
        "metric_key": ini.metric_key,
        "target_value": ini.target_value,
        "target_metric": ini.target_metric,
        "target_change": ini.target_change,
        "owner": ini.owner,
        "due_date": ini.due_date.isoformat() if ini.due_date else None,
        "baseline_window_start": ini.baseline_window_start.isoformat() if ini.baseline_window_start else None,
        "baseline_window_end": ini.baseline_window_end.isoformat() if ini.baseline_window_end else None,
        "baseline_metrics": ini.baseline_metrics_json,
        "implementation_date": ini.implementation_date.isoformat() if ini.implementation_date else None,
        "implementation_description": ini.implementation_description,
        "do_owner": ini.do_owner,
        "do_status": ini.do_status,
        "customers_informed": ini.customers_informed,
        "customers_informed_date": ini.customers_informed_date.isoformat() if ini.customers_informed_date else None,
        "customers_informed_notes": ini.customers_informed_notes,
        "check_computed_at": ini.check_computed_at.isoformat() if ini.check_computed_at else None,
        "check_post_n": ini.check_post_n,
        "check_sufficient_data": ini.check_sufficient_data,
        "check_results": ini.check_results_json,
        "act_decision": ini.act_decision,
        "act_notes": ini.act_notes,
        "created_at": ini.created_at.isoformat() if ini.created_at else None,
        "updated_at": ini.updated_at.isoformat() if ini.updated_at else None,
    }


# ── Status ────────────────────────────────────────────────────────────────────

@router.get("/status")
async def action_layer_status(
    enabled: bool = Depends(is_action_layer_enabled),
) -> dict:
    return {"enabled": enabled}


# ── Settings ──────────────────────────────────────────────────────────────────

@router.get("/settings")
async def get_settings(
    session: AsyncSession = Depends(_db_session_dependency),
    enabled: bool = Depends(is_action_layer_enabled),
    current_user=Depends(get_current_user),
):
    if not enabled:
        return disabled_response()
    if current_user.role not in ("admin", "supervisor"):
        raise HTTPException(status_code=403, detail="Admin or supervisor required")
    row = await _get_settings_row(session)
    if row is None:
        return JSONResponse({"enabled": False, "message": "No settings row found"})
    return JSONResponse({
        "id": row.id,
        "enabled": row.enabled,
        "as_of_mode": row.as_of_mode,
        "commitment_due_soon_hours": row.commitment_due_soon_hours,
        "high_impact_reasons": row.high_impact_reasons_json,
    })


@router.post("/settings")
async def update_settings(
    body: SettingsUpdate,
    session: AsyncSession = Depends(_db_session_dependency),
    enabled: bool = Depends(is_action_layer_enabled),
    current_user=Depends(get_current_user),
):
    if not enabled:
        return disabled_response()
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin required")
    row = await _get_settings_row(session)
    if row is None:
        row = ActSettings(enabled=True)
        session.add(row)
    if body.enabled is not None:
        row.enabled = body.enabled
    if body.as_of_mode is not None:
        if body.as_of_mode not in ("dataset_max", "realtime", "manual"):
            raise HTTPException(400, "as_of_mode must be dataset_max, realtime, or manual")
        row.as_of_mode = body.as_of_mode
    if body.commitment_due_soon_hours is not None:
        row.commitment_due_soon_hours = body.commitment_due_soon_hours
    if body.high_impact_reasons_json is not None:
        row.high_impact_reasons_json = body.high_impact_reasons_json
    session.add(AuditLog(
        user_id=current_user.id,
        action="action_layer_settings_updated",
        resource_type="act_settings",
        resource_id=str(row.id or "new"),
        details_json=body.model_dump(exclude_none=True),
    ))
    await session.commit()
    return JSONResponse({"status": "ok", "enabled": row.enabled})


# ── Demo seed ─────────────────────────────────────────────────────────────────

@router.post("/seed-demo")
async def seed_demo(
    session: AsyncSession = Depends(_db_session_dependency),
    current_user=Depends(get_current_user),
):
    # No enabled gate — this endpoint is the bootstrap that creates the enabled state.
    if current_user.role != "admin":
        raise HTTPException(403, "Admin required")
    from backend.action_layer.demo_seeder import seed_demonstration
    result = await seed_demonstration(session=session, user_id=current_user.id)
    await session.commit()
    return JSONResponse(result)


# ── Derive ────────────────────────────────────────────────────────────────────

@router.post("/derive")
async def derive_items(
    force: bool = Query(default=False),
    session: AsyncSession = Depends(_db_session_dependency),
    enabled: bool = Depends(is_action_layer_enabled),
    current_user=Depends(get_current_user),
):
    if not enabled:
        return disabled_response()
    if current_user.role != "admin":
        raise HTTPException(403, "Admin required")
    from backend.action_layer.derive_job import derive_all_pending
    result = await derive_all_pending(session=session, force=force)
    await session.commit()
    return JSONResponse(result)


@router.post("/derive-issues")
async def derive_issues(
    session: AsyncSession = Depends(_db_session_dependency),
    enabled: bool = Depends(is_action_layer_enabled),
    current_user=Depends(get_current_user),
):
    if not enabled:
        return disabled_response()
    if current_user.role != "admin":
        raise HTTPException(403, "Admin required")
    from backend.action_layer.issues_derive_job import derive_recurring_issues
    result = await derive_recurring_issues(session=session)
    await session.commit()
    return JSONResponse(result)


# ── Items (Recovery Desk) ─────────────────────────────────────────────────────

@router.get("/items")
async def list_items(
    priority: str | None = Query(default=None),
    status: str | None = Query(default=None),
    intervention_type: str | None = Query(default=None),
    risk_band: str | None = Query(default=None),
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0),
    session: AsyncSession = Depends(_db_session_dependency),
    enabled: bool = Depends(is_action_layer_enabled),
    current_user=Depends(get_current_user),
):
    if not enabled:
        return disabled_response()
    q = select(ActItem).where(ActItem.current == True)
    if priority:
        q = q.where(ActItem.priority == priority)
    if status:
        q = q.where(ActItem.status == status)
    if intervention_type:
        q = q.where(ActItem.intervention_type == intervention_type)
    if risk_band:
        q = q.where(ActItem.risk_band == risk_band)
    q = q.order_by(
        ActItem.priority.asc(),
        ActItem.risk_index.desc(),
        ActItem.created_at.desc(),
    ).offset(offset).limit(limit)
    rows = (await session.execute(q)).scalars().all()
    return JSONResponse({
        "enabled": True,
        "items": [_item_to_dict(r) for r in rows],
        "count": len(rows),
        "offset": offset,
        "limit": limit,
    })


@router.get("/items/{item_id}")
async def get_item(
    item_id: int,
    session: AsyncSession = Depends(_db_session_dependency),
    enabled: bool = Depends(is_action_layer_enabled),
    current_user=Depends(get_current_user),
):
    if not enabled:
        return disabled_response()
    item = (await session.execute(
        select(ActItem).where(ActItem.id == item_id)
    )).scalars().first()
    if not item:
        raise HTTPException(404, "Item not found")

    recs = (await session.execute(
        select(ActRecommendation).where(ActRecommendation.item_id == item_id)
        .order_by(ActRecommendation.rank)
    )).scalars().all()

    events = (await session.execute(
        select(ActRecommendation).where(ActRecommendation.item_id == item_id)
    )).scalars().all()

    return JSONResponse({
        "enabled": True,
        "item": _item_to_dict(item),
        "risk_components": item.risk_components_json,
        "recommendations": [
            {
                "rank": r.rank,
                "action_key": r.action_key,
                "title": r.title,
                "justification": r.justification,
                "signal_refs": r.signal_refs_json,
                "playbook_rule_id": r.playbook_rule_id,
                "constraint_note": r.constraint_note,
            }
            for r in recs
        ],
    })


@router.post("/items/{item_id}/transition")
async def transition_item_endpoint(
    item_id: int,
    body: TransitionRequest,
    session: AsyncSession = Depends(_db_session_dependency),
    enabled: bool = Depends(is_action_layer_enabled),
    current_user=Depends(get_current_user),
):
    if not enabled:
        return disabled_response()
    try:
        result = await transition_item(
            item_id=item_id,
            to_status=body.to_status,
            actor_user_id=current_user.id,
            actor_role=current_user.role,
            session=session,
            notes=body.notes,
            outcome=body.outcome,
            dismissal_reason=body.dismissal_reason,
        )
    except WorkflowError as e:
        raise HTTPException(status_code=422, detail={"code": e.code, "message": e.detail})
    await session.commit()
    return JSONResponse({"enabled": True, **result})


@router.get("/items/{item_id}/draft")
async def get_item_draft(
    item_id: int,
    session: AsyncSession = Depends(_db_session_dependency),
    enabled: bool = Depends(is_action_layer_enabled),
    current_user=Depends(get_current_user),
):
    if not enabled:
        return disabled_response()
    draft = (await session.execute(
        select(ActDraft).where(ActDraft.item_id == item_id)
        .order_by(ActDraft.created_at.desc()).limit(1)
    )).scalars().first()
    if not draft:
        raise HTTPException(404, "No draft found for this item")
    return JSONResponse({
        "enabled": True,
        "draft": {
            "id": draft.id,
            "item_id": draft.item_id,
            "kind": draft.kind,
            "content": draft.content,
            "facts_used": draft.facts_used_json,
            "placeholders": draft.placeholders_json,
            "gate_status": draft.gate_status,
            "created_at": draft.created_at.isoformat() if draft.created_at else None,
        },
    })


@router.post("/items/{item_id}/what-if")
async def item_what_if(
    item_id: int,
    body: WhatIfRequest,
    session: AsyncSession = Depends(_db_session_dependency),
    enabled: bool = Depends(is_action_layer_enabled),
    current_user=Depends(get_current_user),
):
    if not enabled:
        return disabled_response()
    item = (await session.execute(
        select(ActItem).where(ActItem.id == item_id)
    )).scalars().first()
    if not item:
        raise HTTPException(404, "Item not found")

    # Rebuild RiskResult from stored components
    comps = [
        RiskComponent(
            name=c["name"],
            points=c["points"],
            triggered=c["triggered"],
            rule=c.get("rule", ""),
            evidence_ref=c.get("evidence_ref", {}),
            description=c.get("description", ""),
        )
        for c in (item.risk_components_json or [])
    ]
    risk = RiskResult(
        risk_index=item.risk_index,
        risk_band=item.risk_band,
        components=comps,
    )
    scenario = compute_what_if(risk, body.clear_components)
    return JSONResponse({"enabled": True, "scenario": scenario})


# ── Recurring Issues ──────────────────────────────────────────────────────────

@router.get("/issues")
async def list_issues(
    session: AsyncSession = Depends(_db_session_dependency),
    enabled: bool = Depends(is_action_layer_enabled),
    current_user=Depends(get_current_user),
):
    if not enabled:
        return disabled_response()
    rows = (await session.execute(
        select(ActRecurringIssue)
        .where(ActRecurringIssue.current == True)
        .order_by(ActRecurringIssue.volume.desc())
    )).scalars().all()
    return JSONResponse({
        "enabled": True,
        "issues": [_issue_to_dict(r) for r in rows],
        "count": len(rows),
    })


@router.get("/issues/{issue_id}")
async def get_issue(
    issue_id: int,
    session: AsyncSession = Depends(_db_session_dependency),
    enabled: bool = Depends(is_action_layer_enabled),
    current_user=Depends(get_current_user),
):
    if not enabled:
        return disabled_response()
    issue = (await session.execute(
        select(ActRecurringIssue).where(ActRecurringIssue.id == issue_id)
    )).scalars().first()
    if not issue:
        raise HTTPException(404, "Issue not found")
    suggestions = (await session.execute(
        select(ActPreventionSuggestion).where(ActPreventionSuggestion.issue_id == issue_id)
    )).scalars().all()
    return JSONResponse({
        "enabled": True,
        "issue": _issue_to_dict(issue),
        "prevention_suggestions": [
            {
                "id": s.id,
                "suggestion_text": s.suggestion_text,
                "suggested_owner": s.suggested_owner,
                "prevention_rule_id": s.prevention_rule_id,
                "evidence": s.evidence_json,
                "label": "Hypothesis for human validation",
            }
            for s in suggestions
        ],
    })


# ── PDCA Initiatives ──────────────────────────────────────────────────────────

@router.get("/initiatives")
async def list_initiatives(
    stage: str | None = Query(default=None),
    session: AsyncSession = Depends(_db_session_dependency),
    enabled: bool = Depends(is_action_layer_enabled),
    current_user=Depends(get_current_user),
):
    if not enabled:
        return disabled_response()
    q = select(ActInitiative)
    if stage:
        q = q.where(ActInitiative.stage == stage)
    q = q.order_by(ActInitiative.created_at.desc())
    rows = (await session.execute(q)).scalars().all()
    return JSONResponse({
        "enabled": True,
        "initiatives": [_initiative_to_dict(r) for r in rows],
        "count": len(rows),
    })


@router.get("/initiatives/{initiative_id}")
async def get_initiative(
    initiative_id: int,
    session: AsyncSession = Depends(_db_session_dependency),
    enabled: bool = Depends(is_action_layer_enabled),
    current_user=Depends(get_current_user),
):
    if not enabled:
        return disabled_response()
    ini = (await session.execute(
        select(ActInitiative).where(ActInitiative.id == initiative_id)
    )).scalars().first()
    if not ini:
        raise HTTPException(404, "Initiative not found")
    events = (await session.execute(
        select(ActInitiativeEvent).where(ActInitiativeEvent.initiative_id == initiative_id)
        .order_by(ActInitiativeEvent.created_at)
    )).scalars().all()
    return JSONResponse({
        "enabled": True,
        "initiative": _initiative_to_dict(ini),
        "stage_history": [
            {
                "from_stage": e.from_stage,
                "to_stage": e.to_stage,
                "notes": e.notes,
                "created_at": e.created_at.isoformat() if e.created_at else None,
            }
            for e in events
        ],
    })


@router.post("/initiatives")
async def create_initiative(
    body: InitiativeCreate,
    session: AsyncSession = Depends(_db_session_dependency),
    enabled: bool = Depends(is_action_layer_enabled),
    current_user=Depends(get_current_user),
):
    if not enabled:
        return disabled_response()
    if current_user.role not in ("admin", "supervisor"):
        raise HTTPException(403, "Admin or supervisor required")

    # Parse due_date
    due_date = None
    if body.due_date:
        from datetime import datetime
        try:
            due_date = datetime.fromisoformat(body.due_date)
        except ValueError:
            raise HTTPException(400, "Invalid due_date format; use ISO 8601")

    ini = ActInitiative(
        issue_id=body.issue_id,
        title=body.title,
        stage="plan",
        iteration=1,
        demonstration=False,
        problem_statement=body.problem_statement,
        root_cause_hypothesis=body.root_cause_hypothesis,
        metric_key=body.metric_key,
        target_value=body.target_value,
        target_metric=body.target_metric,
        target_change=body.target_change,
        owner=body.owner,
        due_date=due_date,
    )
    session.add(ini)
    await session.flush()
    session.add(AuditLog(
        user_id=current_user.id,
        action="action_layer_initiative_created",
        resource_type="act_initiative",
        resource_id=str(ini.id),
        details_json={"title": body.title, "issue_id": body.issue_id},
    ))
    await session.commit()
    return JSONResponse({"enabled": True, "initiative": _initiative_to_dict(ini)}, status_code=201)


VALID_STAGES = {"plan", "do", "check", "act"}
VALID_ACT_DECISIONS = {"standardize", "adjust", "abandon"}

STAGE_ORDER = {"plan": 0, "do": 1, "check": 2, "act": 3}


@router.put("/initiatives/{initiative_id}")
async def update_initiative(
    initiative_id: int,
    body: InitiativeUpdate,
    session: AsyncSession = Depends(_db_session_dependency),
    enabled: bool = Depends(is_action_layer_enabled),
    current_user=Depends(get_current_user),
):
    if not enabled:
        return disabled_response()
    if current_user.role not in ("admin", "supervisor"):
        raise HTTPException(403, "Admin or supervisor required")

    ini = (await session.execute(
        select(ActInitiative).where(ActInitiative.id == initiative_id)
    )).scalars().first()
    if not ini:
        raise HTTPException(404, "Initiative not found")

    old_stage = ini.stage

    # ── Stage advance with validation gates ───────────────────────────────────
    if body.stage is not None:
        if body.stage not in VALID_STAGES:
            raise HTTPException(400, f"stage must be one of: {sorted(VALID_STAGES)}")
        if (STAGE_ORDER.get(body.stage, -1) < STAGE_ORDER.get(old_stage, 0)
                and body.stage != "plan"):
            raise HTTPException(400, "Cannot move stage backwards (except to plan for a new iteration)")

        # Gate: Plan → Do requires metric_key + target_value
        new_metric_key = body.metric_key if body.metric_key is not None else ini.metric_key
        new_target_value = body.target_value if body.target_value is not None else ini.target_value
        if body.stage == "do" and old_stage == "plan":
            if not new_metric_key:
                raise HTTPException(400, detail={
                    "message": "Cannot advance to Do: metric key is required.",
                    "field": "metric_key",
                })
            if new_target_value is None:
                raise HTTPException(400, detail={
                    "message": "Cannot advance to Do: numeric target value is required.",
                    "field": "target_value",
                })

        # Gate: Do → Check requires implementation_description + implementation_date
        new_impl_desc = body.implementation_description if body.implementation_description is not None else ini.implementation_description
        new_impl_date = ini.implementation_date  # will be updated below if provided
        if body.implementation_date:
            try:
                from datetime import datetime as _dt
                new_impl_date = _dt.fromisoformat(body.implementation_date)
            except ValueError:
                pass
        if body.stage == "check" and old_stage == "do":
            if not new_impl_desc:
                raise HTTPException(400, detail={
                    "message": "Cannot advance to Check: implementation description is required.",
                    "field": "implementation_description",
                })
            if not new_impl_date:
                raise HTTPException(400, detail={
                    "message": "Cannot advance to Check: implementation date is required.",
                    "field": "implementation_date",
                })

        ini.stage = body.stage

    # ── Act: adjust decision creates a new iteration back to Plan ─────────────
    creating_new_iteration = False
    if body.act_decision == "adjust" and old_stage == "act":
        creating_new_iteration = True

    if body.implementation_date is not None:
        from datetime import datetime
        try:
            ini.implementation_date = datetime.fromisoformat(body.implementation_date)
        except ValueError:
            raise HTTPException(400, "Invalid implementation_date")

    # PLAN field updates
    if body.problem_statement is not None:
        ini.problem_statement = body.problem_statement
    if body.root_cause_hypothesis is not None:
        ini.root_cause_hypothesis = body.root_cause_hypothesis
    if body.metric_key is not None:
        ini.metric_key = body.metric_key
    if body.target_value is not None:
        ini.target_value = body.target_value
    if body.owner is not None:
        ini.owner = body.owner
    if body.due_date is not None:
        from datetime import datetime as _dt2
        try:
            ini.due_date = _dt2.fromisoformat(body.due_date)
        except ValueError:
            raise HTTPException(400, "Invalid due_date")

    # DO field updates
    if body.implementation_description is not None:
        ini.implementation_description = body.implementation_description
    if body.do_owner is not None:
        ini.do_owner = body.do_owner
    if body.do_status is not None:
        ini.do_status = body.do_status
    if body.customers_informed is not None:
        ini.customers_informed = body.customers_informed
    if body.customers_informed_notes is not None:
        ini.customers_informed_notes = body.customers_informed_notes

    # ACT field updates
    if body.act_decision is not None:
        if body.act_decision not in VALID_ACT_DECISIONS:
            raise HTTPException(400, f"act_decision must be one of: {sorted(VALID_ACT_DECISIONS)}")
        ini.act_decision = body.act_decision
    if body.act_notes is not None:
        ini.act_notes = body.act_notes

    # ── Adjust → new iteration: reset DO/CHECK/ACT fields, bump iteration ────
    if creating_new_iteration:
        ini.iteration += 1
        ini.stage = "plan"
        # Clear Do, Check, Act fields for fresh iteration
        ini.implementation_date = None
        ini.implementation_description = ""
        ini.do_owner = ""
        ini.do_status = ""
        ini.customers_informed = None
        ini.customers_informed_date = None
        ini.customers_informed_notes = ""
        ini.check_computed_at = None
        ini.check_post_window_start = None
        ini.check_post_window_end = None
        ini.check_post_n = None
        ini.check_sufficient_data = False
        ini.check_results_json = {}
        ini.act_decision = None
        ini.act_notes = ""
        # Keep baseline frozen — do NOT reset baseline_metrics_json
        session.add(ActInitiativeEvent(
            initiative_id=ini.id,
            from_stage=old_stage,
            to_stage="plan",
            actor_user_id=current_user.id,
            notes=f"Iteration {ini.iteration} started (adjust). {body.notes or ''}".strip(),
        ))

    # Record stage transition event (non-adjust)
    if not creating_new_iteration and body.stage and body.stage != old_stage:
        session.add(ActInitiativeEvent(
            initiative_id=ini.id,
            from_stage=old_stage,
            to_stage=body.stage,
            actor_user_id=current_user.id,
            notes=body.notes or "",
        ))

    session.add(AuditLog(
        user_id=current_user.id,
        action="action_layer_initiative_updated",
        resource_type="act_initiative",
        resource_id=str(ini.id),
        details_json=body.model_dump(exclude_none=True),
    ))
    await session.commit()
    return JSONResponse({"enabled": True, "initiative": _initiative_to_dict(ini)})


# ── Agent Insights ────────────────────────────────────────────────────────────

@router.get("/agents/{agent_id}/profile")
async def agent_profile(
    agent_id: str,
    session: AsyncSession = Depends(_db_session_dependency),
    enabled: bool = Depends(is_action_layer_enabled),
    current_user=Depends(get_current_user),
):
    if not enabled:
        return disabled_response()
    repo = CoreRepository(session)
    from backend.action_layer.derive_job import _get_settings, get_as_of
    settings = await _get_settings(session)
    as_of = await get_as_of(settings, repo)
    agent_info = await repo.get_agent(agent_id)
    convs = await repo.list_analyzed_conversations(agent_id=agent_id, limit=200)

    from backend.action_layer.agent_insights import compute_agent_profile
    profile = compute_agent_profile(
        agent_id=agent_id,
        agent_info=agent_info,
        analyzed_conversations=convs,
        as_of=as_of,
    )
    return JSONResponse({"enabled": True, "profile": profile})


