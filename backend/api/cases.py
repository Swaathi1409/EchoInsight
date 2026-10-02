"""
Case linking API.

Cases group related conversations together (e.g., a customer calling multiple times
about the same issue).

Routes:
  POST /api/v1/cases                          - create case
  GET  /api/v1/cases                          - list cases
  GET  /api/v1/cases/{case_id}                - get case with linked conversations
  PATCH /api/v1/cases/{case_id}               - update case title/status/notes
  POST /api/v1/cases/{case_id}/conversations  - link a conversation to a case
  DELETE /api/v1/cases/{case_id}/conversations/{conv_id} - unlink
"""
from __future__ import annotations
import logging
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import get_current_user
from backend.api.audit import audit_log
from backend.db import _db_session_dependency
from backend.models import Case, CaseConversation, Conversation, User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/cases", tags=["cases"])


class CreateCaseRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=256)
    external_id: str | None = None
    notes: str = ""
    conversation_ids: list[str] = Field(default_factory=list, description="Optional initial conversations to link")


class UpdateCaseRequest(BaseModel):
    title: str | None = None
    status: str | None = None
    notes: str | None = None
    external_id: str | None = None


class LinkConversationRequest(BaseModel):
    conversation_id: str


def _case_resp(case: Case, conversations: list[dict]) -> dict:
    return {
        "case_id": case.case_id,
        "title": case.title,
        "status": case.status,
        "external_id": case.external_id,
        "notes": case.notes,
        "created_at": case.created_at.isoformat() if case.created_at else None,
        "updated_at": case.updated_at.isoformat() if case.updated_at else None,
        "conversation_count": len(conversations),
        "conversations": conversations,
    }


@router.post("", status_code=201)
async def create_case(
    body: CreateCaseRequest,
    session: AsyncSession = Depends(_db_session_dependency),
    user: User = Depends(get_current_user),
) -> dict:
    """Create a new case and optionally link conversations to it."""
    case_id = str(uuid.uuid4())
    case = Case(
        case_id=case_id,
        title=body.title,
        external_id=body.external_id,
        notes=body.notes,
        status="open",
        created_by=user.id,
    )
    session.add(case)
    await session.flush()

    linked = []
    for conv_id in body.conversation_ids:
        conv = await session.get(Conversation, conv_id)
        if not conv:
            continue
        link = CaseConversation(case_id=case_id, conversation_id=conv_id, linked_by=user.id)
        session.add(link)
        linked.append({"conversation_id": conv_id})

    await session.flush()
    await audit_log(session, user_id=user.id, action="create_case",
                    resource_type="case", resource_id=case_id,
                    details={"title": body.title, "linked_count": len(linked)})
    return _case_resp(case, linked)


@router.get("")
async def list_cases(
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
    session: AsyncSession = Depends(_db_session_dependency),
    user: User = Depends(get_current_user),
) -> list[dict]:
    """List cases with optional status filter."""
    q = select(Case).order_by(Case.created_at.desc())
    if status:
        q = q.where(Case.status == status)
    q = q.offset(offset).limit(limit)
    cases = (await session.execute(q)).scalars().all()

    result = []
    for case in cases:
        links = (await session.execute(
            select(CaseConversation).where(CaseConversation.case_id == case.case_id)
        )).scalars().all()
        result.append(_case_resp(case, [{"conversation_id": l.conversation_id} for l in links]))
    return result


@router.get("/{case_id}")
async def get_case(
    case_id: str,
    session: AsyncSession = Depends(_db_session_dependency),
    user: User = Depends(get_current_user),
) -> dict:
    """Get a case with all linked conversations."""
    case = await session.get(Case, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    links = (await session.execute(
        select(CaseConversation).where(CaseConversation.case_id == case_id)
    )).scalars().all()

    conversations = []
    for link in links:
        conv = await session.get(Conversation, link.conversation_id)
        if conv:
            conversations.append({
                "conversation_id": conv.id,
                "status": conv.status,
                "started_at": conv.started_at.isoformat() if conv.started_at else None,
                "turn_count": getattr(conv, "turn_count", None),
                "linked_at": link.linked_at.isoformat() if getattr(link, "linked_at", None) else None,
            })
    return _case_resp(case, conversations)


@router.patch("/{case_id}")
async def update_case(
    case_id: str,
    body: UpdateCaseRequest,
    session: AsyncSession = Depends(_db_session_dependency),
    user: User = Depends(get_current_user),
) -> dict:
    """Update case title, status, or notes."""
    case = await session.get(Case, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    if body.title is not None:
        case.title = body.title
    if body.status is not None:
        if body.status not in ("open", "closed", "escalated"):
            raise HTTPException(status_code=422, detail="status must be open|closed|escalated")
        case.status = body.status
    if body.notes is not None:
        case.notes = body.notes
    if body.external_id is not None:
        case.external_id = body.external_id

    await session.flush()
    await audit_log(session, user_id=user.id, action="update_case",
                    resource_type="case", resource_id=case_id,
                    details=body.model_dump(exclude_none=True))
    links = (await session.execute(
        select(CaseConversation).where(CaseConversation.case_id == case_id)
    )).scalars().all()
    return _case_resp(case, [{"conversation_id": l.conversation_id} for l in links])


@router.post("/{case_id}/conversations", status_code=201)
async def link_conversation(
    case_id: str,
    body: LinkConversationRequest,
    session: AsyncSession = Depends(_db_session_dependency),
    user: User = Depends(get_current_user),
) -> dict:
    """Link a conversation to a case."""
    case = await session.get(Case, case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    conv = await session.get(Conversation, body.conversation_id)
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    existing = (await session.execute(
        select(CaseConversation).where(
            CaseConversation.case_id == case_id,
            CaseConversation.conversation_id == body.conversation_id,
        )
    )).scalar_one_or_none()
    if existing:
        raise HTTPException(status_code=409, detail="Conversation already linked to this case")

    link = CaseConversation(case_id=case_id, conversation_id=body.conversation_id, linked_by=user.id)
    session.add(link)
    await session.flush()
    await audit_log(session, user_id=user.id, action="link_conversation",
                    resource_type="case", resource_id=case_id,
                    details={"conversation_id": body.conversation_id})
    return {"case_id": case_id, "conversation_id": body.conversation_id, "linked": True}


@router.delete("/{case_id}/conversations/{conv_id}", status_code=200)
async def unlink_conversation(
    case_id: str,
    conv_id: str,
    session: AsyncSession = Depends(_db_session_dependency),
    user: User = Depends(get_current_user),
) -> dict:
    """Unlink a conversation from a case."""
    link = (await session.execute(
        select(CaseConversation).where(
            CaseConversation.case_id == case_id,
            CaseConversation.conversation_id == conv_id,
        )
    )).scalar_one_or_none()
    if not link:
        raise HTTPException(status_code=404, detail="Link not found")
    await session.delete(link)
    await session.flush()
    await audit_log(session, user_id=user.id, action="unlink_conversation",
                    resource_type="case", resource_id=case_id,
                    details={"conversation_id": conv_id})
    return {"case_id": case_id, "conversation_id": conv_id, "unlinked": True}
