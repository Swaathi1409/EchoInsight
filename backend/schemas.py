"""
Pydantic v2 schemas for the EchoInsight API.

These schemas define the request and response contracts.
They are separate from the SQLAlchemy ORM models (backend/models.py).
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

try:
    from backend.domain_model import (
        ActionEventType,
        CallReason,
        ChurnRisk,
        CommitmentStatus,
        ConversationEndReason,
        ConversationStatus,
        CustomerSentiment,
        EvidenceType,
        FindingType,
        JobStatus,
        JobType,
        QACheckItemId,
        QACheckResult,
        ResolutionStatus,
        SpeakerRole,
        TurnExtractionStatus,
        UserRole,
        VerificationResult,
    )
except ImportError:
    from domain_model import (  # type: ignore[no-redef]
        CallReason,
        ChurnRisk,
        CommitmentStatus,
        ConversationEndReason,
        ConversationStatus,
        CustomerSentiment,
        FindingType,
        JobStatus,
        JobType,
        QACheckItemId,
        ResolutionStatus,
        SpeakerRole,
        TurnExtractionStatus,
        UserRole,
    )


# ---------------------------------------------------------------------------
# Shared primitives
# ---------------------------------------------------------------------------


class EvidenceQuote(BaseModel):
    """An exact-quote evidence reference grounded in a stored turn."""
    turn_id: str = Field(description="Turn ID (e.g., turn_0003)")
    quote: str = Field(description="Exact substring of the turn's redacted text")


class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class PaginatedResponse(BaseModel):
    total: int
    page: int
    page_size: int
    items: list[Any]


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds


class UserInfo(BaseModel):
    id: int
    username: str
    role: UserRole
    agent_id: str | None
    team_id: str | None


# ---------------------------------------------------------------------------
# Conversation
# ---------------------------------------------------------------------------


class CreateConversationRequest(BaseModel):
    source_id: str | None = Field(None, description="Original dataset conversation ID (32-char hex)")
    channel: str = Field(default="call", description="Channel type (call, chat)")
    synthetic_assignment: bool = Field(default=True)
    case_id: str | None = Field(None, description="Optional case group ID to link related conversations")


class ConversationSummary(BaseModel):
    id: str
    source_id: str | None
    agent_id: str | None
    team_id: str | None
    channel: str
    status: ConversationStatus
    started_at: datetime
    ended_at: datetime | None
    end_reason: ConversationEndReason | None
    turn_count: int
    synthetic_assignment: bool
    analysis_version: int
    case_id: str | None = None
    resumed_from: str | None = None
    # Denormalized from latest analysis for list view
    qa_score: float | None = None
    churn_risk: str | None = None
    false_resolution: bool | None = None
    resolution: str | None = None
    reasons: list[str] | None = None


class ConversationDetail(ConversationSummary):
    turns: list[TurnResponse]
    provisional_state: ProvisionalStateResponse | None
    analysis: AnalysisResponse | None


# ---------------------------------------------------------------------------
# Turns
# ---------------------------------------------------------------------------


class AppendTurnRequest(BaseModel):
    speaker: SpeakerRole
    text: str = Field(min_length=1, max_length=32000)
    timestamp: datetime | None = None
    idempotency_key: str = Field(description="Client-generated unique key for this turn append")


class AppendTurnResponse(BaseModel):
    turn_id: str
    seq: int
    speaker: SpeakerRole
    text_redacted: str
    extraction_status: TurnExtractionStatus
    provisional_state: ProvisionalStateResponse | None
    ledger: list[CommitmentResponse]


class TurnResponse(BaseModel):
    turn_id: str
    seq: int
    speaker: SpeakerRole
    timestamp: datetime | None
    text_redacted: str
    content_hash: str
    extraction_status: TurnExtractionStatus


class SubmitTranscriptRequest(BaseModel):
    source_id: str | None = None
    channel: str = "call"
    turns: list[AppendTurnRequest] = Field(min_length=1)
    synthetic_assignment: bool = True


class SubmitTranscriptResponse(BaseModel):
    conversation_id: str
    job_id: str
    status: str = "queued"


# ---------------------------------------------------------------------------
# Provisional state
# ---------------------------------------------------------------------------


class ProvisionalStateResponse(BaseModel):
    provisional: bool = True
    conversation_id: str
    as_of_turn_id: str
    resolution: ResolutionStatus
    sentiment_current: CustomerSentiment
    sentiment_trajectory: list[SentimentPoint]
    reasons: list[CallReason] = Field(default_factory=list)
    churn_risk: ChurnRisk
    open_commitments: list[CommitmentResponse] = Field(default_factory=list)
    stale: bool = Field(default=False, description="True if extraction is queued and state may be outdated")
    updated_at: datetime


class SentimentPoint(BaseModel):
    turn_id: str
    sentiment: CustomerSentiment


# ---------------------------------------------------------------------------
# Commitments
# ---------------------------------------------------------------------------


class CommitmentResponse(BaseModel):
    commitment_id: str
    provisional: bool
    description: str
    owner: str | None
    deadline: str | None
    deadline_flag: str | None  # e.g., "relative_date_no_timezone"
    status: CommitmentStatus
    created_at_turn_id: str
    completed_at_turn_id: str | None
    carried_over: bool = False
    is_overdue: bool = False
    evidence: list[EvidenceQuote]


# ---------------------------------------------------------------------------
# Analysis
# ---------------------------------------------------------------------------


class AnalysisResponse(BaseModel):
    analysis_id: str
    conversation_id: str
    version: int
    provisional: bool
    model: str
    prompt_version: str
    policy_version: str
    taxonomy_version: int
    summary: str
    reasons: list[CallReason]
    resolution: ResolutionStatus
    churn_risk: ChurnRisk
    churn_signals: list[str]
    sentiment_trajectory: list[SentimentPoint]
    sentiment_start: CustomerSentiment | None = None
    sentiment_end: CustomerSentiment | None = None
    commitments: list[CommitmentResponse]
    qa_result: QAResultResponse | None = None
    false_resolution: bool
    false_resolution_reason: str | None
    created_at: datetime


class SentimentTrajectoryResponse(BaseModel):
    conversation_id: str
    trajectory: list[SentimentPoint]
    start: CustomerSentiment
    end: CustomerSentiment
    direction: str  # "improving", "worsening", "flat", "unknown"


# ---------------------------------------------------------------------------
# QA
# ---------------------------------------------------------------------------


class QAResultResponse(BaseModel):
    qa_result_id: str
    conversation_id: str
    analysis_version: int
    checklist_version: str
    score: float | None  # None if coverage below threshold
    score_label: str  # "score", "partial", "not_assessed"
    coverage: float
    items_applicable: int
    items_assessed: int
    items_needs_review: int
    critical_violation: bool
    items: list[QAItemResponse]


class QAItemResponse(BaseModel):
    """
    Flexible QA item response — tolerates both the raw scorer output format
    (flat: quote/turn_id inline) and the full gated pipeline format.
    All non-identity fields are optional to prevent 500s from schema mismatches.
    """
    model_config = {"extra": "ignore", "populate_by_name": True}

    item_id: str  # raw string; validation via QACheckItemId would reject stored strings
    display: str = ""
    result: str  # pass / fail / needs_review / not_applicable
    score_contribution: float = 0.0
    weight: float = 1.0
    explanation: str = ""
    # Evidence may be stored as a flat quote/turn_id or as a list of EvidenceQuote
    evidence: list[EvidenceQuote] = []
    evidence_type: str | None = None
    finding_type: str | None = None
    confidence: float = 1.0
    human_review_required: bool = False
    verification_result: str | None = None
    policy_reference: str | None = None
    # Flat fields from scorer output
    quote: str | None = None
    turn_id: str | None = None


class ComplianceFindingResponse(BaseModel):
    finding_id: str
    conversation_id: str
    item_id: QACheckItemId
    finding_type: FindingType
    description: str
    evidence: list[EvidenceQuote]
    policy_reference: str
    reviewed: bool
    review_outcome: str | None


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------


class JobResponse(BaseModel):
    job_id: str
    job_type: JobType
    status: JobStatus
    conversation_id: str
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    attempts: int
    error: str | None


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------


class AgentAnalytics(BaseModel):
    agent_id: str
    synthetic_assignment: bool = True
    conversation_count: int
    avg_qa_score: float | None
    avg_coverage: float
    critical_violations: int
    false_resolutions: int
    open_commitments: int
    resolution_rate: float
    sentiment_worsening_rate: float


class TeamAnalytics(BaseModel):
    team_id: str
    synthetic_assignment: bool = True
    agent_count: int
    conversation_count: int
    avg_qa_score: float | None
    avg_coverage: float
    critical_violations: int
    false_resolutions: int
    open_commitments: int
    resolution_rate: float


class KPIResponse(BaseModel):
    conversations_analyzed: int
    conversations_pending: int
    resolution_rate: float
    avg_qa_score: float | None
    avg_coverage: float
    critical_violations_count: int
    open_commitments_count: int
    items_needs_review_count: int
    false_resolutions_count: int
    date_from: datetime | None
    date_to: datetime | None


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


class HealthResponse(BaseModel):
    status: str = "ok"


class ReadyResponse(BaseModel):
    status: str
    database: str
    migrations: str


# ---------------------------------------------------------------------------
# Error
# ---------------------------------------------------------------------------


class ErrorResponse(BaseModel):
    code: str
    message: str
    request_id: str
