"""
Conversations router:
  POST   /api/v1/conversations                  - create
  GET    /api/v1/conversations                  - list (scoped)
  GET    /api/v1/conversations/{id}             - detail
  POST   /api/v1/conversations/{id}/turns       - append turn (returns provisional state)
  POST   /api/v1/conversations/{id}/end         - end conversation
  POST   /api/v1/conversations/submit           - batch transcript submit
  GET    /api/v1/conversations/{id}/analysis    - get analysis result
  GET    /api/v1/conversations/{id}/jobs        - job status
  GET    /api/v1/conversations/open-commitments - open commitment queue
  GET    /api/v1/conversations/false-resolutions - false resolution list
  GET    /api/v1/analytics/agent/{agent_id}     - agent analytics
  GET    /api/v1/analytics/team/{team_id}       - team analytics
"""
from __future__ import annotations
import hashlib, logging, uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.deps import get_current_user
from backend.db import _db_session_dependency
from backend.domain_model import (
    ConversationStatus, JobStatus, JobType,
    TurnExtractionStatus, UserRole, TURN_ID_FORMAT
)
from backend.ingest.assignment import assign, AGENT_NAMES, TEAM_NAMES
from backend.ingest.redactor import redact_turn
from backend.models import (
    Agent, Analysis, Conversation, Job, QAResult, Team, Turn, User
)
from backend.schemas import (
    AppendTurnRequest, AppendTurnResponse, ConversationDetail,
    ConversationSummary, CreateConversationRequest, JobResponse,
    SubmitTranscriptRequest, SubmitTranscriptResponse, TurnResponse
)
from backend.state.reducer import apply_turn_extraction, initial_state

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/v1/conversations", tags=["conversations"])
analytics_router = APIRouter(prefix="/api/v1/analytics", tags=["analytics"])


# ── helpers ──────────────────────────────────────────────────────────────────

async def _ensure_agent_team(session: AsyncSession, agent_id: str, team_id: str) -> None:
    """Create synthetic agent/team rows if they don't exist."""
    from backend.ingest.assignment import AGENT_NAMES, TEAM_NAMES
    if not (await session.get(Team, team_id)):
        session.add(Team(team_id=team_id, display_name=TEAM_NAMES.get(team_id, team_id),
                         synthetic_assignment=True))
    if not (await session.get(Agent, agent_id)):
        session.add(Agent(agent_id=agent_id, display_name=AGENT_NAMES.get(agent_id, agent_id),
                          team_id=team_id, synthetic_assignment=True))
    await session.flush()


def _scope_filter(user: User):
    """Return SQLAlchemy filter clauses based on user role."""
    if user.role == UserRole.AGENT.value:
        return [Conversation.agent_id == user.agent_id]
    if user.role == UserRole.SUPERVISOR.value:
        return [Conversation.team_id == user.team_id]
    return []  # admin sees all


# ── routes ───────────────────────────────────────────────────────────────────

@router.post("", response_model=ConversationSummary, status_code=201)
async def create_conversation(
    body: CreateConversationRequest,
    session=Depends(_db_session_dependency),
    user: User = Depends(get_current_user),
) -> ConversationSummary:
    conv_id = str(uuid.uuid4())
    agent_id, team_id = assign(conv_id)
    await _ensure_agent_team(session, agent_id, team_id)

    conv = Conversation(
        id=conv_id,
        source_id=body.source_id,
        agent_id=agent_id,
        team_id=team_id,
        channel=body.channel,
        status=ConversationStatus.ACTIVE.value,
        synthetic_assignment=True,
    )
    session.add(conv)
    await session.flush()
    return _conv_summary(conv, 0)


@router.get("", response_model=list[ConversationSummary])
async def list_conversations(
    session=Depends(_db_session_dependency),
    user: User = Depends(get_current_user),
    limit: int = 50,
    offset: int = 0,
    status: str | None = None,
) -> list[ConversationSummary]:
    from sqlalchemy import func
    filters = _scope_filter(user)
    q = select(Conversation).order_by(Conversation.started_at.desc()).offset(offset).limit(limit)
    if filters:
        q = q.where(*filters)
    if status:
        q = q.where(Conversation.status == status)
    rows = (await session.execute(q)).scalars().all()

    # Batch turn counts
    conv_ids = [c.id for c in rows]
    if conv_ids:
        tc_q = (
            select(Turn.conversation_id, func.count(Turn.turn_id).label("tc"))
            .where(Turn.conversation_id.in_(conv_ids))
            .group_by(Turn.conversation_id)
        )
        tc_map = {r.conversation_id: r.tc for r in (await session.execute(tc_q)).all()}
    else:
        tc_map = {}

    # Batch latest analysis QA data
    if conv_ids:
        from backend.models import Analysis, QAResult
        an_q = (
            select(
                Analysis.conversation_id,
                Analysis.churn_risk,
                Analysis.false_resolution,
                QAResult.score,
            )
            .join(QAResult, QAResult.analysis_id == Analysis.analysis_id, isouter=True)
            .where(
                Analysis.conversation_id.in_(conv_ids),
                Analysis.provisional == False,  # noqa: E712
            )
            .order_by(Analysis.version.desc())
        )
        an_rows = (await session.execute(an_q)).all()
        # Keep only highest version per conv (already ordered desc, take first seen)
        an_map: dict = {}
        for ar in an_rows:
            if ar.conversation_id not in an_map:
                an_map[ar.conversation_id] = ar
    else:
        an_map = {}

    summaries = []
    for c in rows:
        tc = tc_map.get(c.id, 0)
        ar = an_map.get(c.id)
        summaries.append(_conv_summary(
            c, tc,
            qa_score=ar.score if ar else None,
            churn_risk=ar.churn_risk if ar else None,
            false_resolution=ar.false_resolution if ar else None,
        ))
    return summaries


@router.get("/{conv_id}", response_model=ConversationDetail)
async def get_conversation(
    conv_id: str,
    session=Depends(_db_session_dependency),
    user: User = Depends(get_current_user),
) -> ConversationDetail:
    conv = await _get_or_404(conv_id, session, user)
    turns_rows = (await session.execute(
        select(Turn).where(Turn.conversation_id == conv_id).order_by(Turn.seq)
    )).scalars().all()
    turns = [_turn_resp(t) for t in turns_rows]

    # Latest analysis
    analysis_resp = None
    an_row = (await session.execute(
        select(Analysis).where(Analysis.conversation_id == conv_id)
        .order_by(Analysis.version.desc()).limit(1)
    )).scalar_one_or_none()
    if an_row:
        qa_row = (await session.execute(
            select(QAResult).where(QAResult.analysis_id == an_row.analysis_id)
        )).scalar_one_or_none()
        analysis_resp = _analysis_resp(an_row, qa_row)

    return ConversationDetail(
        **_conv_summary(conv, len(turns)).__dict__,
        turns=turns,
        provisional_state=None,
        analysis=analysis_resp,
    )


@router.post("/{conv_id}/turns", response_model=AppendTurnResponse, status_code=201)
async def append_turn(
    conv_id: str,
    body: AppendTurnRequest,
    response: Response,
    session=Depends(_db_session_dependency),
    user: User = Depends(get_current_user),
) -> AppendTurnResponse:
    conv = await _get_or_404(conv_id, session, user)
    if conv.status == ConversationStatus.ENDED.value:
        raise HTTPException(status_code=409, detail="Conversation has ended; no more turns can be appended")

    # Idempotency check
    existing = (await session.execute(
        select(Turn).where(
            Turn.conversation_id == conv_id,
            Turn.idempotency_key == body.idempotency_key,
        )
    )).scalar_one_or_none()
    if existing:
        prov = conv.provisional_state_json or {}
        response.status_code = 200  # idempotent replay
        return _append_resp(existing, prov, prov.get("commitments", []))

    # Redact
    redacted = redact_turn(body.speaker.value, body.text)
    content_hash = hashlib.sha256(redacted.encode()).hexdigest()

    # Seq number
    existing_turns = (await session.execute(
        select(Turn).where(Turn.conversation_id == conv_id).order_by(Turn.seq.desc()).limit(1)
    )).scalar_one_or_none()
    seq = (existing_turns.seq + 1) if existing_turns else 1
    turn_id = TURN_ID_FORMAT.format(seq=seq)

    turn = Turn(
        turn_id=turn_id,
        conversation_id=conv_id,
        seq=seq,
        speaker=body.speaker.value,
        timestamp=body.timestamp or datetime.now(timezone.utc),
        text_redacted=redacted,
        content_hash=content_hash,
        idempotency_key=body.idempotency_key,
        extraction_status=TurnExtractionStatus.PENDING.value,
    )
    session.add(turn)
    await session.flush()

    # Update provisional state synchronously with a lightweight (no-LLM) turn event.
    # The full per-turn LLM extraction job updates this asynchronously.
    current_state = conv.provisional_state_json or initial_state(conv_id)
    # Minimal extraction — no LLM, just register the turn in state
    lightweight_extraction = {
        "resolution_update": "no_change",
        "sentiment": "neutral",
        "churn_signal": "none",
        "new_commitments": [],
        "completed_commitments": [],
    }
    updated_state = apply_turn_extraction(current_state, lightweight_extraction, turn_id, redacted)
    updated_state["provisional"] = True
    conv.provisional_state_json = updated_state
    await session.flush()

    # Enqueue per-turn extraction job (async LLM update)
    job = Job(
        job_id=str(uuid.uuid4()),
        job_type=JobType.PER_TURN_EXTRACTION.value,
        status=JobStatus.QUEUED.value,
        conversation_id=conv_id,
        idempotency_key=f"turn-extract-{turn_id}-{conv_id}",
        payload_json={"turn_id": turn_id, "seq": seq},
    )
    session.add(job)
    await session.flush()

    commitments = updated_state.get("commitments", [])
    return _append_resp(turn, updated_state, commitments)


@router.post("/{conv_id}/end", status_code=202)
async def end_conversation(
    conv_id: str,
    session=Depends(_db_session_dependency),
    user: User = Depends(get_current_user),
) -> dict:
    conv = await _get_or_404(conv_id, session, user)
    if conv.status == ConversationStatus.ENDED.value:
        raise HTTPException(status_code=409, detail="Conversation is already ended")

    conv.status = ConversationStatus.ENDED.value
    conv.ended_at = datetime.now(timezone.utc)

    job = Job(
        job_id=str(uuid.uuid4()),
        job_type=JobType.FINAL_ANALYSIS.value,
        status=JobStatus.QUEUED.value,
        conversation_id=conv_id,
        idempotency_key=f"final-analysis-{conv_id}",
        payload_json={},
    )
    session.add(job)
    await session.flush()
    return {"status": "ended", "conversation_id": conv_id, "job_id": job.job_id}


@router.post("/submit", response_model=SubmitTranscriptResponse, status_code=202)
async def submit_transcript(
    body: SubmitTranscriptRequest,
    session=Depends(_db_session_dependency),
    user: User = Depends(get_current_user),
) -> SubmitTranscriptResponse:
    """Batch ingest: create conversation, append all turns, end it, queue analysis."""
    conv_id = str(uuid.uuid4())
    agent_id, team_id = assign(conv_id)
    await _ensure_agent_team(session, agent_id, team_id)

    conv = Conversation(
        id=conv_id, source_id=body.source_id, agent_id=agent_id, team_id=team_id,
        channel=body.channel, status=ConversationStatus.ENDED.value,
        ended_at=datetime.now(timezone.utc), synthetic_assignment=True,
    )
    session.add(conv)
    await session.flush()

    for i, t in enumerate(body.turns, start=1):
        redacted = redact_turn(t.speaker.value, t.text)
        turn = Turn(
            turn_id=TURN_ID_FORMAT.format(seq=i),
            conversation_id=conv_id, seq=i,
            speaker=t.speaker.value,
            timestamp=t.timestamp or datetime.now(timezone.utc),
            text_redacted=redacted,
            content_hash=hashlib.sha256(redacted.encode()).hexdigest(),
            idempotency_key=t.idempotency_key,
            extraction_status=TurnExtractionStatus.PENDING.value,
        )
        session.add(turn)

    job = Job(
        job_id=str(uuid.uuid4()),
        job_type=JobType.FINAL_ANALYSIS.value,
        status=JobStatus.QUEUED.value,
        conversation_id=conv_id,
        idempotency_key=f"final-analysis-{conv_id}",
        payload_json={},
    )
    session.add(job)
    await session.flush()
    return SubmitTranscriptResponse(conversation_id=conv_id, job_id=job.job_id)


@router.get("/{conv_id}/analysis")
async def get_analysis(conv_id: str, session=Depends(_db_session_dependency),
                       user: User = Depends(get_current_user)) -> dict:
    await _get_or_404(conv_id, session, user)
    an = (await session.execute(
        select(Analysis).where(Analysis.conversation_id == conv_id)
        .order_by(Analysis.version.desc()).limit(1)
    )).scalar_one_or_none()
    if an is None:
        # Check if job is queued/running
        job = (await session.execute(
            select(Job).where(Job.conversation_id == conv_id,
                              Job.job_type == JobType.FINAL_ANALYSIS.value)
            .order_by(Job.created_at.desc()).limit(1)
        )).scalar_one_or_none()
        status_str = job.status if job else "not_started"
        raise HTTPException(202, detail={"status": status_str, "message": "Analysis not yet complete"})
    qa = (await session.execute(
        select(QAResult).where(QAResult.analysis_id == an.analysis_id)
    )).scalar_one_or_none()
    return _analysis_resp(an, qa)


@router.get("/{conv_id}/jobs", response_model=list[JobResponse])
async def list_jobs(conv_id: str, session=Depends(_db_session_dependency),
                    user: User = Depends(get_current_user)) -> list[JobResponse]:
    await _get_or_404(conv_id, session, user)
    jobs = (await session.execute(
        select(Job).where(Job.conversation_id == conv_id).order_by(Job.created_at.desc())
    )).scalars().all()
    return [_job_resp(j) for j in jobs]


# ── private helpers ───────────────────────────────────────────────────────────

async def _get_or_404(conv_id: str, session: AsyncSession, user: User) -> Conversation:
    conv = await session.get(Conversation, conv_id)
    if conv is None:
        raise HTTPException(404, "Conversation not found")
    # Scope check
    if user.role == UserRole.AGENT.value and conv.agent_id != user.agent_id:
        raise HTTPException(403, "Access denied")
    if user.role == UserRole.SUPERVISOR.value and conv.team_id != user.team_id:
        raise HTTPException(403, "Access denied")
    return conv


def _conv_summary(
    conv: Conversation,
    turn_count: int,
    qa_score: float | None = None,
    churn_risk: str | None = None,
    false_resolution: bool | None = None,
) -> ConversationSummary:
    return ConversationSummary(
        id=conv.id, source_id=conv.source_id, agent_id=conv.agent_id,
        team_id=conv.team_id, channel=conv.channel, status=conv.status,
        started_at=conv.started_at, ended_at=conv.ended_at,
        end_reason=conv.end_reason, turn_count=turn_count,
        synthetic_assignment=conv.synthetic_assignment,
        analysis_version=conv.analysis_version,
        qa_score=qa_score,
        churn_risk=churn_risk,
        false_resolution=false_resolution,
    )


def _turn_resp(t: Turn) -> TurnResponse:
    return TurnResponse(
        turn_id=t.turn_id, seq=t.seq, speaker=t.speaker,
        timestamp=t.timestamp, text_redacted=t.text_redacted,
        content_hash=t.content_hash, extraction_status=t.extraction_status,
    )


def _append_resp(turn: Turn, state: dict, ledger: list) -> AppendTurnResponse:
    # Raw reducer state stored in DB; typed schema served via GET /conversations/{id}
    return AppendTurnResponse(
        turn_id=turn.turn_id, seq=turn.seq, speaker=turn.speaker,
        text_redacted=turn.text_redacted,
        extraction_status=turn.extraction_status,
        provisional_state=None,
        ledger=ledger,
    )


def _analysis_resp(an: Analysis, qa: QAResult | None) -> dict:
    d = {
        "analysis_id": an.analysis_id, "conversation_id": an.conversation_id,
        "version": an.version, "provisional": an.provisional, "model": an.model,
        "prompt_version": an.prompt_version, "policy_version": an.policy_version,
        "taxonomy_version": an.taxonomy_version, "summary": an.summary,
        "reasons": an.reasons_json, "resolution": an.resolution,
        "churn_risk": an.churn_risk, "churn_signals": an.churn_signals_json,
        "sentiment_trajectory": an.sentiment_trajectory_json,
        "false_resolution": an.false_resolution,
        "false_resolution_reason": an.false_resolution_reason,
        "commitments": [], "created_at": an.created_at,
        "qa_result": None,
    }
    if qa:
        d["qa_result"] = {
            "qa_result_id": qa.qa_result_id, "conversation_id": qa.conversation_id,
            "analysis_version": qa.analysis_version, "checklist_version": qa.checklist_version,
            "score": qa.score, "score_label": qa.score_label, "coverage": qa.coverage,
            "items_applicable": qa.items_applicable, "items_assessed": qa.items_assessed,
            "items_needs_review": qa.items_needs_review, "critical_violation": qa.critical_violation,
            "items": qa.items_json,
        }
    return d


def _job_resp(j: Job) -> JobResponse:
    return JobResponse(
        job_id=j.job_id, job_type=j.job_type, status=j.status,
        conversation_id=j.conversation_id, created_at=j.created_at,
        started_at=j.started_at, completed_at=j.completed_at,
        attempts=j.attempts, error=j.error,
    )


# ── Open Commitment Queue ────────────────────────────────────────────────────

@router.get("/open-commitments")
async def open_commitments(
    session=Depends(_db_session_dependency),
    user: User = Depends(get_current_user),
    limit: int = Query(50, le=200),
    offset: int = 0,
) -> list[dict]:
    """Return conversations with open (non-completed) commitments at end."""
    filters = _scope_filter(user)
    q = select(Conversation).where(Conversation.status == ConversationStatus.ENDED.value)
    if filters:
        q = q.where(*filters)
    q = q.order_by(Conversation.ended_at.desc()).offset(offset).limit(limit)
    rows = (await session.execute(q)).scalars().all()
    result = []
    for conv in rows:
        prov = conv.provisional_state_json or {}
        open_c = [c for c in prov.get("commitments", [])
                  if c.get("status") not in ("completed", "cancelled")]
        if open_c:
            result.append({
                "conversation_id": conv.id, "agent_id": conv.agent_id,
                "team_id": conv.team_id, "ended_at": conv.ended_at.isoformat() if conv.ended_at else None,
                "open_commitments": open_c,
                "synthetic_assignment": conv.synthetic_assignment,
            })
    return result


# ── False Resolution Queue ────────────────────────────────────────────────────

@router.get("/false-resolutions")
async def false_resolutions(
    session=Depends(_db_session_dependency),
    user: User = Depends(get_current_user),
    limit: int = Query(50, le=200),
    offset: int = 0,
) -> list[dict]:
    """Return conversations flagged as false resolutions by the detector."""
    filters = _scope_filter(user)
    q = (select(Analysis)
         .join(Conversation, Analysis.conversation_id == Conversation.id)
         .where(Analysis.false_resolution == True))
    if filters:
        q = q.where(*filters)
    q = q.order_by(Analysis.created_at.desc()).offset(offset).limit(limit)
    rows = (await session.execute(q)).scalars().all()
    return [{
        "conversation_id": an.conversation_id, "analysis_id": an.analysis_id,
        "version": an.version, "false_resolution_reason": an.false_resolution_reason,
        "resolution": an.resolution, "created_at": an.created_at,
    } for an in rows]


# ── Analytics ─────────────────────────────────────────────────────────────────

@analytics_router.get("/agent/{agent_id}")
async def agent_analytics(
    agent_id: str,
    session=Depends(_db_session_dependency),
    user: User = Depends(get_current_user),
) -> dict:
    """Agent-level QA rollup. Agents see only their own; supervisors see their team's; admins see all."""
    # Scope check
    if user.role == UserRole.AGENT.value and user.agent_id != agent_id:
        raise HTTPException(403, "Access denied")
    if user.role == UserRole.SUPERVISOR.value:
        agent_row = await session.get(Agent, agent_id)
        if not agent_row or agent_row.team_id != user.team_id:
            raise HTTPException(403, "Access denied")

    conv_ids_q = select(Conversation.id).where(
        Conversation.agent_id == agent_id,
        Conversation.status == ConversationStatus.ENDED.value,
    )
    conv_ids = [r for r in (await session.execute(conv_ids_q)).scalars().all()]
    if not conv_ids:
        return {"agent_id": agent_id, "conversations": 0, "avg_qa_score": None,
                "critical_violations": 0, "false_resolutions": 0}

    qa_rows = (await session.execute(
        select(QAResult).where(QAResult.conversation_id.in_(conv_ids))
    )).scalars().all()

    scores = [q.score for q in qa_rows if q.score is not None and q.score_label != "partial"]
    avg_score = round(sum(scores) / len(scores), 1) if scores else None
    critical = sum(1 for q in qa_rows if q.critical_violation)

    fr_count = (await session.execute(
        select(func.count()).select_from(Analysis)
        .where(Analysis.conversation_id.in_(conv_ids), Analysis.false_resolution == True)
    )).scalar_one()

    return {
        "agent_id": agent_id,
        "conversations": len(conv_ids),
        "conversations_with_qa": len(qa_rows),
        "avg_qa_score": avg_score,
        "critical_violations": critical,
        "false_resolutions": fr_count,
        "synthetic_assignment": True,
    }


@analytics_router.get("/team/{team_id}")
async def team_analytics(
    team_id: str,
    session=Depends(_db_session_dependency),
    user: User = Depends(get_current_user),
) -> dict:
    """Team-level QA rollup. Supervisors see only their team; admins see all."""
    if user.role == UserRole.AGENT.value:
        raise HTTPException(403, "Access denied")
    if user.role == UserRole.SUPERVISOR.value and user.team_id != team_id:
        raise HTTPException(403, "Access denied")

    conv_ids_q = select(Conversation.id).where(
        Conversation.team_id == team_id,
        Conversation.status == ConversationStatus.ENDED.value,
    )
    conv_ids = [r for r in (await session.execute(conv_ids_q)).scalars().all()]
    if not conv_ids:
        return {"team_id": team_id, "conversations": 0, "avg_qa_score": None,
                "critical_violations": 0, "false_resolutions": 0}

    qa_rows = (await session.execute(
        select(QAResult).where(QAResult.conversation_id.in_(conv_ids))
    )).scalars().all()

    scores = [q.score for q in qa_rows if q.score is not None and q.score_label != "partial"]
    avg_score = round(sum(scores) / len(scores), 1) if scores else None
    critical = sum(1 for q in qa_rows if q.critical_violation)

    fr_count = (await session.execute(
        select(func.count()).select_from(Analysis)
        .where(Analysis.conversation_id.in_(conv_ids), Analysis.false_resolution == True)
    )).scalar_one()

    agents = (await session.execute(
        select(Conversation.agent_id, func.count().label("cnt"))
        .where(Conversation.team_id == team_id, Conversation.status == ConversationStatus.ENDED.value)
        .group_by(Conversation.agent_id)
    )).all()

    return {
        "team_id": team_id,
        "conversations": len(conv_ids),
        "conversations_with_qa": len(qa_rows),
        "avg_qa_score": avg_score,
        "critical_violations": critical,
        "false_resolutions": fr_count,
        "agent_breakdown": [{"agent_id": a, "conversations": c} for a, c in agents],
        "synthetic_assignment": True,
    }
