"""
Admin and reviewer API routes:
  GET  /api/v1/audit-logs                   - paginated audit log (admin/supervisor)
  GET  /api/v1/conversations/{id}/reviews   - list reviews for a conversation
  POST /api/v1/conversations/{id}/reviews   - create reviewer annotation
  PATCH /api/v1/qa-results/{qa_id}/annotate - annotate a QA item with human verdict
  GET  /api/v1/checklists                   - list checklist policy versions
  POST /api/v1/checklists                   - create new checklist version
  GET  /api/v1/checklists/{version}         - get specific version
  PATCH /api/v1/checklists/{version}        - update (creates new version)
"""
from __future__ import annotations

import logging
import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.audit import audit_log
from backend.api.deps import get_current_user
from backend.db import _db_session_dependency
from backend.domain_model import UserRole
from backend.models import AuditLog, Conversation, QAResult, ReviewAnnotation, User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1", tags=["admin"])


# ---------------------------------------------------------------------------
# Permission helpers
# ---------------------------------------------------------------------------

def _require_admin(user: User) -> None:
    if user.role != UserRole.ADMIN.value:
        raise HTTPException(status_code=403, detail="Admin role required")


def _require_supervisor_or_above(user: User) -> None:
    if user.role not in (UserRole.ADMIN.value, UserRole.SUPERVISOR.value):
        raise HTTPException(status_code=403, detail="Supervisor or admin role required")


# ---------------------------------------------------------------------------
# Audit log read endpoint
# ---------------------------------------------------------------------------

class AuditLogEntry(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    user_id: int | None
    action: str
    resource_type: str
    resource_id: str
    details: dict[str, Any]
    created_at: datetime


@router.get("/audit-logs", response_model=list[AuditLogEntry])
async def list_audit_logs(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    resource_type: str | None = Query(None),
    resource_id: str | None = Query(None),
    action: str | None = Query(None),
    session: AsyncSession = Depends(_db_session_dependency),
    user: User = Depends(get_current_user),
) -> list[AuditLogEntry]:
    """Paginated audit log. Admin only."""
    _require_admin(user)

    q = select(AuditLog).order_by(desc(AuditLog.created_at))
    if resource_type:
        q = q.where(AuditLog.resource_type == resource_type)
    if resource_id:
        q = q.where(AuditLog.resource_id == resource_id)
    if action:
        q = q.where(AuditLog.action == action)
    q = q.offset(offset).limit(limit)

    rows = (await session.execute(q)).scalars().all()
    return [
        AuditLogEntry(
            id=r.id,
            user_id=r.user_id,
            action=r.action,
            resource_type=r.resource_type,
            resource_id=r.resource_id,
            details=r.details_json or {},
            created_at=r.created_at,
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Reviewer workflow
# ---------------------------------------------------------------------------

# NOTE: Reviews are persisted to the review_annotations table (D16 fix).
# The old in-memory _review_store has been removed.


class CreateReviewRequest(BaseModel):
    verdict: str = Field(..., description="approved | rejected | needs_rework")
    notes: str = Field(default="")
    qa_override: dict[str, str] = Field(
        default_factory=dict,
        description="item_id -> pass|fail|not_applicable override"
    )


class ReviewResponse(BaseModel):
    review_id: str
    conversation_id: str
    reviewer_id: int
    verdict: str
    notes: str
    qa_override: dict[str, str]
    created_at: str


@router.get("/conversations/{conv_id}/reviews", response_model=list[ReviewResponse])
async def list_reviews(
    conv_id: str,
    session: AsyncSession = Depends(_db_session_dependency),
    user: User = Depends(get_current_user),
) -> list[ReviewResponse]:
    """List all reviewer annotations for a conversation."""
    _require_supervisor_or_above(user)
    rows = (await session.execute(
        select(ReviewAnnotation)
        .where(ReviewAnnotation.conversation_id == conv_id)
        .order_by(ReviewAnnotation.created_at.asc())
    )).scalars().all()
    import json as _json
    return [
        ReviewResponse(
            review_id=r.review_id,
            conversation_id=r.conversation_id,
            reviewer_id=r.reviewer_id,
            verdict=r.verdict,
            notes=r.notes or "",
            qa_override=_json.loads(r.qa_override_json) if r.qa_override_json else {},
            created_at=r.created_at.isoformat() if r.created_at else "",
        )
        for r in rows
    ]


@router.post("/conversations/{conv_id}/reviews", response_model=ReviewResponse, status_code=201)
async def create_review(
    conv_id: str,
    body: CreateReviewRequest,
    session: AsyncSession = Depends(_db_session_dependency),
    user: User = Depends(get_current_user),
) -> ReviewResponse:
    """Submit a reviewer annotation for a conversation."""
    _require_supervisor_or_above(user)

    # Verify conversation exists
    conv = await session.get(Conversation, conv_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    if body.verdict not in ("approved", "rejected", "needs_rework"):
        raise HTTPException(status_code=422, detail="verdict must be approved|rejected|needs_rework")

    import json as _json
    review_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    annotation = ReviewAnnotation(
        review_id=review_id,
        conversation_id=conv_id,
        reviewer_id=user.id,
        verdict=body.verdict,
        notes=body.notes,
        qa_override_json=_json.dumps(body.qa_override) if body.qa_override else None,
        created_at=now,
    )
    session.add(annotation)
    await session.flush()

    await audit_log(session, user_id=user.id, action="create_review",
                    resource_type="conversation", resource_id=conv_id,
                    details={"verdict": body.verdict, "review_id": review_id,
                             "overrides": len(body.qa_override)})
    return ReviewResponse(
        review_id=review_id,
        conversation_id=conv_id,
        reviewer_id=user.id,
        verdict=body.verdict,
        notes=body.notes,
        qa_override=body.qa_override,
        created_at=now.isoformat(),
    )


# ---------------------------------------------------------------------------
# QA item annotation (human verdict override)
# ---------------------------------------------------------------------------

class QAAnnotateRequest(BaseModel):
    item_id: str
    human_verdict: str = Field(..., description="pass|fail|not_applicable")
    note: str = Field(default="")


class QAAnnotateResponse(BaseModel):
    qa_result_id: str
    item_id: str
    human_verdict: str
    note: str
    annotated_by: int
    annotated_at: str


# In-memory; production: add QAAnnotation table
_qa_annotations: dict[str, list[dict]] = {}


@router.patch("/qa-results/{qa_result_id}/annotate", response_model=QAAnnotateResponse)
async def annotate_qa_item(
    qa_result_id: str,
    body: QAAnnotateRequest,
    session: AsyncSession = Depends(_db_session_dependency),
    user: User = Depends(get_current_user),
) -> QAAnnotateResponse:
    """Human reviewer overrides a QA item verdict."""
    _require_supervisor_or_above(user)

    if body.human_verdict not in ("pass", "fail", "not_applicable"):
        raise HTTPException(status_code=422, detail="human_verdict must be pass|fail|not_applicable")

    # Verify QA result exists
    qa = await session.get(QAResult, qa_result_id)
    if not qa:
        raise HTTPException(status_code=404, detail="QA result not found")

    annotation = QAAnnotateResponse(
        qa_result_id=qa_result_id,
        item_id=body.item_id,
        human_verdict=body.human_verdict,
        note=body.note,
        annotated_by=user.id,
        annotated_at=datetime.now(UTC).isoformat(),
    )
    _qa_annotations.setdefault(qa_result_id, []).append(annotation.model_dump())

    await audit_log(session, user_id=user.id, action="annotate_qa_item",
                    resource_type="qa_result", resource_id=qa_result_id,
                    details={"item_id": body.item_id, "human_verdict": body.human_verdict})
    return annotation


# ---------------------------------------------------------------------------
# Checklist admin CRUD with versioning
# ---------------------------------------------------------------------------

from backend.models import QAChecklist, QAChecklistItem, QAChecklistVersion


class ChecklistItemSchema(BaseModel):
    item_key: str
    display_name: str
    description: str | None = None
    weight: float = 1.0
    critical: bool = False
    required: bool = False
    enabled: bool = True
    display_order: int = 0
    evaluation_type: str = "llm_contextual"
    policy_reference: str | None = None
    applicability_note: str | None = None

class ChecklistVersionSchema(BaseModel):
    version_number: int
    status: str
    created_at: str
    items: list[ChecklistItemSchema]
    settings: dict

class CreateChecklistRequest(BaseModel):
    name: str
    description: str | None = None
    items: list[ChecklistItemSchema]
    settings: dict | None = None

class UpdateChecklistRequest(BaseModel):
    status: str | None = None
    # Add items to create a new version
    items: list[ChecklistItemSchema] | None = None
    settings: dict | None = None


@router.get("/checklists", response_model=list[dict])
async def list_checklists(
    session: AsyncSession = Depends(_db_session_dependency),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """List all available checklist policy versions."""
    _require_supervisor_or_above(user)

    # Get checklists with their active versions
    q = select(QAChecklist, QAChecklistVersion).outerjoin(
        QAChecklistVersion,
        (QAChecklist.id == QAChecklistVersion.checklist_id) & (QAChecklistVersion.status == "active")
    )
    rows = (await session.execute(q)).all()

    result = []
    for checklist, active_ver in rows:
        result.append({
            "key": checklist.key,
            "name": checklist.name,
            "description": checklist.description,
            "active_version": active_ver.version_number if active_ver else None,
            "active_version_id": active_ver.id if active_ver else None,
            "updated_at": active_ver.created_at.isoformat() if active_ver else None,
        })
    return result


@router.get("/checklists/{key}", response_model=dict)
async def get_checklist(
    key: str,
    session: AsyncSession = Depends(_db_session_dependency),
    user: User = Depends(get_current_user),
) -> dict:
    """Get a specific checklist and its active version."""
    _require_supervisor_or_above(user)
    q = select(QAChecklist).where(QAChecklist.key == key)
    checklist = (await session.execute(q)).scalar_one_or_none()
    if not checklist:
        raise HTTPException(status_code=404, detail=f"Checklist '{key}' not found")

    q_ver = select(QAChecklistVersion).where(
        QAChecklistVersion.checklist_id == checklist.id,
        QAChecklistVersion.status == "active"
    ).order_by(QAChecklistVersion.version_number.desc()).limit(1)
    ver = (await session.execute(q_ver)).scalar_one_or_none()

    items = []
    if ver:
        q_items = select(QAChecklistItem).where(QAChecklistItem.version_id == ver.id).order_by(QAChecklistItem.display_order)
        db_items = (await session.execute(q_items)).scalars().all()
        for i in db_items:
            items.append({
                "item_key": i.item_key,
                "display_name": i.display_name,
                "description": i.description,
                "weight": i.weight,
                "critical": i.critical,
                "required": i.required,
                "enabled": i.enabled,
                "evaluation_type": i.evaluation_type,
            })

    return {
        "key": checklist.key,
        "name": checklist.name,
        "description": checklist.description,
        "active_version": ver.version_number if ver else None,
        "settings": ver.settings if ver else {},
        "items": items
    }


import hashlib
import json


def _compute_hash(data: dict) -> str:
    return hashlib.sha256(json.dumps(data, sort_keys=True).encode('utf-8')).hexdigest()

@router.post("/checklists/{key}/versions", response_model=dict, status_code=201)
async def create_checklist_version(
    key: str,
    body: CreateChecklistRequest,
    session: AsyncSession = Depends(_db_session_dependency),
    user: User = Depends(get_current_user),
) -> dict:
    """Create a new version for a checklist."""
    _require_admin(user)

    q = select(QAChecklist).where(QAChecklist.key == key)
    checklist = (await session.execute(q)).scalar_one_or_none()

    if not checklist:
        # Create checklist if not exists
        checklist = QAChecklist(
            key=key,
            name=body.name,
            description=body.description or ""
        )
        session.add(checklist)
        await session.flush()

    # Find latest version number
    q_latest = select(func.max(QAChecklistVersion.version_number)).where(QAChecklistVersion.checklist_id == checklist.id)
    latest_ver = (await session.execute(q_latest)).scalar() or 0
    new_version_num = latest_ver + 1

    data_dict = body.model_dump()
    content_hash = _compute_hash(data_dict)

    # Create version
    new_ver = QAChecklistVersion(
        checklist_id=checklist.id,
        version_number=new_version_num,
        status="active",
        source="admin_ui",
        created_by=user.username,
        created_at=datetime.now(UTC),
        content_hash=content_hash,
        settings=body.settings or {}
    )
    session.add(new_ver)

    # Deactivate older active versions
    q_deactivate = update(QAChecklistVersion).where(
        QAChecklistVersion.checklist_id == checklist.id,
        QAChecklistVersion.id != new_ver.id,
        QAChecklistVersion.status == "active"
    ).values(status="archived")
    await session.execute(q_deactivate)
    await session.flush()

    for idx, item in enumerate(body.items):
        db_item = QAChecklistItem(
            version_id=new_ver.id,
            item_key=item.item_key,
            display_name=item.display_name,
            description=item.description,
            weight=item.weight,
            required=item.required,
            critical=item.critical,
            enabled=item.enabled,
            display_order=idx,
            evaluation_type=item.evaluation_type,
            policy_reference=item.policy_reference,
            applicability_note=item.applicability_note
        )
        session.add(db_item)

    await audit_log(session, user_id=user.id, action="create_checklist_version",
                    resource_type="checklist", resource_id=key,
                    details={"version_number": new_version_num, "item_count": len(body.items)})

    return {"key": key, "version_number": new_version_num}

class PurgeResponse(BaseModel):
    purged_count: int
    message: str

@router.post("/purge", response_model=PurgeResponse)
async def purge_data(
    days: int = Query(90, description="Purge data older than this many days"),
    session: AsyncSession = Depends(_db_session_dependency),
    user: User = Depends(get_current_user),
) -> PurgeResponse:
    """Purge raw transcripts older than specified days, keeping metadata."""
    _require_admin(user)

    from datetime import timedelta

    from backend.models import Turn

    threshold = datetime.now(UTC) - timedelta(days=days)

    # We redact the text_redacted of turns older than the threshold
    # The requirement says "purges raw transcripts... but keeps aggregated insights"
    q = (
        update(Turn)
        .where(Turn.timestamp < threshold, Turn.text_redacted != "[PURGED]")
        .values(text_redacted="[PURGED]", content_hash="[PURGED]")
    )
    result = await session.execute(q)
    await session.flush()

    await audit_log(session, user_id=user.id, action="purge_data",
                    resource_type="system", resource_id="retention",
                    details={"days": days, "rows_affected": result.rowcount})

    return PurgeResponse(purged_count=result.rowcount, message=f"Purged {result.rowcount} turns older than {days} days")



@router.get('/config')
async def get_config(user: User = Depends(get_current_user)) -> dict:
    'Return current operational config.'
    _require_supervisor_or_above(user)
    from backend.config.settings import get_settings
    s = get_settings()
    return {
        'qa_confidence_threshold': s.qa_confidence_threshold,
        'qa_critical_items': s.qa_critical_items,
        'qa_max_verification_items': s.qa_max_verification_items,
        'llm_primary_model': s.llm_primary_model,
        'store_original_text': s.store_original_text,
    }
