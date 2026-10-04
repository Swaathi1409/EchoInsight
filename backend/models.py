"""
SQLAlchemy 2 ORM models for EchoInsight.

Uses mapped_column and DeclarativeBase for full type annotation support.
PostgreSQL in production; SQLite only in unit tests.
"""
from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy import JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(256), nullable=False)
    role: Mapped[str] = mapped_column(String(16), nullable=False)  # admin, supervisor, agent
    agent_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("agents.agent_id"), nullable=True)
    team_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("teams.team_id"), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_users_username", "username"),
        Index("ix_users_agent_id", "agent_id"),
        Index("ix_users_team_id", "team_id"),
    )


class Agent(Base):
    __tablename__ = "agents"

    agent_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    team_id: Mapped[str] = mapped_column(String(64), ForeignKey("teams.team_id"), nullable=False)
    synthetic_assignment: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Team(Base):
    __tablename__ = "teams"

    team_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    synthetic_assignment: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    source_id: Mapped[str | None] = mapped_column(String(64), nullable=True)  # original dataset conv ID
    agent_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("agents.agent_id"), nullable=True)
    team_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("teams.team_id"), nullable=True)
    channel: Mapped[str] = mapped_column(String(32), default="call", nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="created")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    end_reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
    analysis_version: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    synthetic_assignment: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    provisional_state_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # Tier 2: case_id, resumed_from
    case_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resumed_from: Mapped[str | None] = mapped_column(String(64), ForeignKey("conversations.id"), nullable=True)

    turns: Mapped[list[Turn]] = relationship("Turn", back_populates="conversation", order_by="Turn.seq")
    analyses: Mapped[list[Analysis]] = relationship("Analysis", back_populates="conversation")
    jobs: Mapped[list[Job]] = relationship("Job", back_populates="conversation")
    segments: Mapped[list[Segment]] = relationship("Segment", back_populates="conversation", order_by="Segment.created_at")

    __table_args__ = (
        Index("ix_conversations_source_id", "source_id"),
        Index("ix_conversations_agent_id", "agent_id"),
        Index("ix_conversations_team_id", "team_id"),
        Index("ix_conversations_status", "status"),
        Index("ix_conversations_started_at", "started_at"),
    )


class Turn(Base):
    __tablename__ = "turns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    turn_id: Mapped[str] = mapped_column(String(16), nullable=False)  # turn_0001, turn_0002, etc.
    conversation_id: Mapped[str] = mapped_column(String(64), ForeignKey("conversations.id"), nullable=False)
    seq: Mapped[int] = mapped_column(Integer, nullable=False)
    speaker: Mapped[str] = mapped_column(String(16), nullable=False)
    timestamp: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    text_redacted: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # sha256 of redacted text
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    extraction_status: Mapped[str] = mapped_column(String(16), default="pending", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    conversation: Mapped[Conversation] = relationship("Conversation", back_populates="turns")

    __table_args__ = (
        UniqueConstraint("conversation_id", "seq", name="uq_turn_conv_seq"),
        UniqueConstraint("conversation_id", "idempotency_key", name="uq_turn_idempotency"),
        Index("ix_turns_conversation_id", "conversation_id"),
        Index("ix_turns_turn_id", "turn_id"),
        Index("ix_turns_extraction_status", "extraction_status"),
    )

    @staticmethod
    def compute_content_hash(text_redacted: str) -> str:
        return hashlib.sha256(text_redacted.encode("utf-8")).hexdigest()


class Segment(Base):
    """A segment boundary in a conversation, e.g. after a resume or a long pause."""
    __tablename__ = "segments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(String(64), ForeignKey("conversations.id"), nullable=False)
    start_turn_id: Mapped[str | None] = mapped_column(String(16), nullable=True)
    reason: Mapped[str] = mapped_column(String(32), nullable=False)  # 'resume', 'idle_gap'
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    conversation: Mapped[Conversation] = relationship("Conversation", back_populates="segments")

    __table_args__ = (
        Index("ix_segments_conversation_id", "conversation_id"),
    )


class StateEvent(Base):
    """Append-only log of state changes, used by the reducer."""
    __tablename__ = "state_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(String(64), ForeignKey("conversations.id"), nullable=False)
    turn_id: Mapped[str] = mapped_column(String(16), nullable=False)
    event_type: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    provisional: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_state_events_conversation_id", "conversation_id"),
        Index("ix_state_events_turn_id", "turn_id"),
    )


class Commitment(Base):
    """A follow-up action or commitment made during the conversation."""
    __tablename__ = "commitments"

    commitment_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(String(64), ForeignKey("conversations.id"), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    owner: Mapped[str | None] = mapped_column(String(128), nullable=True)
    deadline: Mapped[str | None] = mapped_column(String(64), nullable=True)
    deadline_flag: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="proposed")
    provisional: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at_turn_id: Mapped[str] = mapped_column(String(16), nullable=False)
    completed_at_turn_id: Mapped[str | None] = mapped_column(String(16), nullable=True)
    carried_over: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    evidence_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        Index("ix_commitments_conversation_id", "conversation_id"),
        Index("ix_commitments_status", "status"),
    )


class Analysis(Base):
    """Versioned analysis result for a conversation."""
    __tablename__ = "analyses"

    analysis_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(String(64), ForeignKey("conversations.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    provisional: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(32), nullable=False)
    policy_version: Mapped[str] = mapped_column(String(32), nullable=False)
    taxonomy_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    reasons_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    resolution: Mapped[str] = mapped_column(String(32), nullable=False)
    churn_risk: Mapped[str] = mapped_column(String(16), nullable=False)
    churn_signals_json: Mapped[list[str]] = mapped_column(JSON, nullable=False)
    sentiment_trajectory_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    false_resolution: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    false_resolution_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    checklist_version_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    conversation: Mapped[Conversation] = relationship("Conversation", back_populates="analyses")
    qa_result: Mapped[QAResult | None] = relationship("QAResult", back_populates="analysis", uselist=False)

    __table_args__ = (
        UniqueConstraint("conversation_id", "version", name="uq_analysis_conv_version"),
        Index("ix_analyses_conversation_id", "conversation_id"),
    )


class QAResult(Base):
    __tablename__ = "qa_results"

    qa_result_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    analysis_id: Mapped[str] = mapped_column(String(64), ForeignKey("analyses.analysis_id"), nullable=False)
    conversation_id: Mapped[str] = mapped_column(String(64), ForeignKey("conversations.id"), nullable=False)
    analysis_version: Mapped[int] = mapped_column(Integer, nullable=False)
    checklist_version: Mapped[str] = mapped_column(String(32), nullable=False) # legacy string
    checklist_version_id: Mapped[int | None] = mapped_column(Integer, nullable=True) # new id
    score: Mapped[float | None] = mapped_column(Float, nullable=True)
    score_label: Mapped[str] = mapped_column(String(32), nullable=False)  # "score", "partial", "not_assessed"
    coverage: Mapped[float] = mapped_column(Float, nullable=False)
    items_applicable: Mapped[int] = mapped_column(Integer, nullable=False)
    items_assessed: Mapped[int] = mapped_column(Integer, nullable=False)
    items_needs_review: Mapped[int] = mapped_column(Integer, nullable=False)
    critical_violation: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    items_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    analysis: Mapped[Analysis] = relationship("Analysis", back_populates="qa_result")

    __table_args__ = (
        Index("ix_qa_results_conversation_id", "conversation_id"),
        Index("ix_qa_results_analysis_id", "analysis_id"),
    )


class Job(Base):
    __tablename__ = "jobs"

    job_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    job_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    conversation_id: Mapped[str] = mapped_column(String(64), ForeignKey("conversations.id"), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    conversation: Mapped[Conversation] = relationship("Conversation", back_populates="jobs")

    __table_args__ = (
        Index("ix_jobs_status", "status"),
        Index("ix_jobs_conversation_id", "conversation_id"),
        Index("ix_jobs_created_at", "created_at"),
    )


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(128), nullable=False)
    details_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_audit_log_user_id", "user_id"),
        Index("ix_audit_log_resource_type", "resource_type"),
        Index("ix_audit_log_created_at", "created_at"),
    )


class Case(Base):
    """A support case grouping one or more conversations."""
    __tablename__ = "cases"

    case_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    external_id: Mapped[str | None] = mapped_column(String(128), nullable=True)  # CRM ticket ID
    title: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open")  # open|closed|escalated
    created_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    notes: Mapped[str] = mapped_column(Text, default="")

    __table_args__ = (
        Index("ix_cases_external_id", "external_id"),
        Index("ix_cases_status", "status"),
    )


class CaseConversation(Base):
    """Many-to-many join: conversations linked to a case."""
    __tablename__ = "case_conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    case_id: Mapped[str] = mapped_column(String(36), ForeignKey("cases.case_id"), nullable=False)
    conversation_id: Mapped[str] = mapped_column(String(36), ForeignKey("conversations.id"), nullable=False)
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    linked_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)

    __table_args__ = (
        UniqueConstraint("case_id", "conversation_id", name="uq_case_conversation"),
        Index("ix_case_conversations_case_id", "case_id"),
        Index("ix_case_conversations_conversation_id", "conversation_id"),
    )


class ReviewAnnotation(Base):
    """Persistent reviewer annotation for a conversation (D16 fix: replaces in-memory store)."""
    __tablename__ = "review_annotations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    review_id: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    conversation_id: Mapped[str] = mapped_column(String(36), ForeignKey("conversations.id"), nullable=False)
    reviewer_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    verdict: Mapped[str] = mapped_column(String(32), nullable=False)  # approved|rejected|needs_rework
    notes: Mapped[str] = mapped_column(Text, default="")
    qa_override_json: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON dict item_id -> pass|fail|na
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_review_annotations_conversation_id", "conversation_id"),
        Index("ix_review_annotations_reviewer_id", "reviewer_id"),
        Index("ix_review_annotations_created_at", "created_at"),
    )


class QAChecklist(Base):
    __tablename__ = "qa_checklist"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class QAChecklistVersion(Base):
    __tablename__ = "qa_checklist_version"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    checklist_id: Mapped[int] = mapped_column(Integer, ForeignKey("qa_checklist.id"), nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False) # draft, active, archived
    source: Mapped[str] = mapped_column(String(32), nullable=False) # yaml_seed, ui, import
    created_by: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    activated_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    change_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    content_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    settings: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)

    __table_args__ = (
        UniqueConstraint("checklist_id", "version_number", name="uq_qa_checklist_version_number"),
        Index("ix_qa_checklist_version_status", "status"),
        Index("ix_qa_checklist_version_active", "checklist_id", "status", unique=True, postgresql_where=(status == 'active'), sqlite_where=(status == 'active')),
    )


class QAChecklistItem(Base):
    __tablename__ = "qa_checklist_item"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    version_id: Mapped[int] = mapped_column(Integer, ForeignKey("qa_checklist_version.id"), nullable=False)
    item_key: Mapped[str] = mapped_column(String(64), nullable=False)
    display_name: Mapped[str] = mapped_column(String(128), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    weight: Mapped[float] = mapped_column(Float, nullable=False)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False)
    critical: Mapped[bool] = mapped_column(Boolean, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)
    evaluation_type: Mapped[str] = mapped_column(String(32), nullable=False)
    policy_reference: Mapped[str | None] = mapped_column(Text, nullable=True)
    applicability_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    __table_args__ = (
        UniqueConstraint("version_id", "item_key", name="uq_qa_checklist_item_key"),
    )
