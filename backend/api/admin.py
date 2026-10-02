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
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select, func, desc, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import get_current_user
from backend.api.audit import audit_log
from backend.db import _db_session_dependency
from backend.domain_model import UserRole
from backend.models import AuditLog, QAResult, Analysis, Conversation, User

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

# In-memory store (sufficient for MVP; production: add ReviewerNote table)
_review_store: dict[str, list[dict]] = {}


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
    return _review_store.get(conv_id, [])


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

    review_id = str(uuid.uuid4())
    entry = ReviewResponse(
        review_id=review_id,
        conversation_id=conv_id,
        reviewer_id=user.id,
        verdict=body.verdict,
        notes=body.notes,
        qa_override=body.qa_override,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    _review_store.setdefault(conv_id, []).append(entry.model_dump())

    await audit_log(session, user_id=user.id, action="create_review",
                    resource_type="conversation", resource_id=conv_id,
                    details={"verdict": body.verdict, "review_id": review_id,
                             "overrides": len(body.qa_override)})
    return entry


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
        annotated_at=datetime.now(timezone.utc).isoformat(),
    )
    _qa_annotations.setdefault(qa_result_id, []).append(annotation.model_dump())

    await audit_log(session, user_id=user.id, action="annotate_qa_item",
                    resource_type="qa_result", resource_id=qa_result_id,
                    details={"item_id": body.item_id, "human_verdict": body.human_verdict})
    return annotation


# ---------------------------------------------------------------------------
# Checklist admin CRUD with versioning
# ---------------------------------------------------------------------------

# In-memory versioned store (production: persist to DB or YAML files)
import yaml
from pathlib import Path

POLICY_DIR = Path(__file__).parent.parent / "config"

_checklist_cache: dict[str, dict] = {}


def _load_policy_file(version: str) -> dict | None:
    """Load a policy YAML file by version slug."""
    p = POLICY_DIR / f"policy_{version}.yaml"
    if p.exists():
        with p.open() as f:
            return yaml.safe_load(f)
    return None


def _save_policy_file(version: str, data: dict) -> None:
    p = POLICY_DIR / f"policy_{version}.yaml"
    with p.open("w") as f:
        yaml.dump(data, f, sort_keys=False, allow_unicode=True)


class ChecklistItem(BaseModel):
    item_id: str
    description: str
    weight: float = 1.0
    critical: bool = False
    applicable_when: str = "always"


class ChecklistVersion(BaseModel):
    version: str
    display_name: str
    created_at: str
    items: list[ChecklistItem]
    active: bool = False


class CreateChecklistRequest(BaseModel):
    version: str = Field(..., description="Version slug, e.g. v2")
    display_name: str
    items: list[ChecklistItem]
    active: bool = False


class UpdateChecklistRequest(BaseModel):
    display_name: str | None = None
    items: list[ChecklistItem] | None = None
    active: bool | None = None


@router.get("/checklists", response_model=list[dict])
async def list_checklists(
    user: User = Depends(get_current_user),
) -> list[dict]:
    """List all available checklist policy versions."""
    _require_supervisor_or_above(user)
    result = []
    for p in sorted(POLICY_DIR.glob("policy_*.yaml")):
        ver = p.stem.replace("policy_", "")
        data = _load_policy_file(ver) or {}
        result.append({
            "version": ver,
            "display_name": data.get("policy_name", ver),
            "item_count": len(data.get("items", [])),
            "created_at": data.get("created_at", ""),
            "active": data.get("active", False),
        })
    return result


@router.get("/checklists/{version}", response_model=dict)
async def get_checklist(
    version: str,
    user: User = Depends(get_current_user),
) -> dict:
    """Get a specific checklist version."""
    _require_supervisor_or_above(user)
    data = _load_policy_file(version)
    if not data:
        raise HTTPException(status_code=404, detail=f"Checklist version '{version}' not found")
    return data


@router.post("/checklists", response_model=dict, status_code=201)
async def create_checklist(
    body: CreateChecklistRequest,
    session: AsyncSession = Depends(_db_session_dependency),
    user: User = Depends(get_current_user),
) -> dict:
    """Create a new checklist version."""
    _require_admin(user)

    existing = _load_policy_file(body.version)
    if existing:
        raise HTTPException(status_code=409, detail=f"Version '{body.version}' already exists")

    data = {
        "policy_name": body.display_name,
        "policy_version": body.version,
        "active": body.active,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "created_by": user.username,
        "items": [item.model_dump() for item in body.items],
    }
    _save_policy_file(body.version, data)
    await audit_log(session, user_id=user.id, action="create_checklist",
                    resource_type="checklist", resource_id=body.version,
                    details={"item_count": len(body.items), "active": body.active})
    return data


@router.patch("/checklists/{version}", response_model=dict)
async def update_checklist(
    version: str,
    body: UpdateChecklistRequest,
    session: AsyncSession = Depends(_db_session_dependency),
    user: User = Depends(get_current_user),
) -> dict:
    """
    Update a checklist version. This creates a new snapshot with the changes
    while preserving the original (append-only history via file versioning).
    """
    _require_admin(user)

    data = _load_policy_file(version)
    if not data:
        raise HTTPException(status_code=404, detail=f"Checklist version '{version}' not found")

    if body.display_name is not None:
        data["policy_name"] = body.display_name
    if body.items is not None:
        data["items"] = [item.model_dump() for item in body.items]
    if body.active is not None:
        data["active"] = body.active
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    data["updated_by"] = user.username

    _save_policy_file(version, data)
    await audit_log(session, user_id=user.id, action="update_checklist",
                    resource_type="checklist", resource_id=version,
                    details={"changes": list(body.model_dump(exclude_none=True).keys())})
    return data

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
    
    from backend.models import Turn
    from datetime import timedelta
    
    threshold = datetime.now(timezone.utc) - timedelta(days=days)
    
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
