"""
backend/assistant/models.py
SQLAlchemy models for assistant tables (asst_* prefix, additive only).
Never modifies or references existing table definitions.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    Boolean, DateTime, Float, ForeignKey, Integer, String, Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

# Import Base from the project's existing model registry so Alembic sees everything.
from backend.models import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_uuid() -> str:
    return str(uuid.uuid4())


class AsstSettings(Base):
    """
    Runtime toggle for the assistant (one row).
    Admin can set enabled=false to silence the assistant without redeploying.
    """
    __tablename__ = "asst_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    model_name: Mapped[str] = mapped_column(String(100), default="", nullable=False)
    rate_limit_per_user_per_hour: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    max_question_chars: Mapped[int] = mapped_column(Integer, default=1000, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )


class AsstSession(Base):
    """
    One session per user browser session. Holds resolved context (entities, filters).
    Cleared when user clicks 'Clear context'.
    """
    __tablename__ = "asst_session"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False)  # users.id
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )
    last_active_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False
    )
    # JSON: { resolved_entities: {}, active_filters: {}, last_3_headlines: [] }
    context_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)

    messages: Mapped[list["AsstMessage"]] = relationship(
        "AsstMessage", back_populates="session", cascade="all, delete-orphan"
    )


class AsstMessage(Base):
    """
    One row per user question or assistant answer. Does NOT store full tool result bodies
    (privacy + size). Stores tool names, param hashes, check outcomes, tokens, latency.
    """
    __tablename__ = "asst_message"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    session_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("asst_session.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(10), nullable=False)  # "user" | "assistant"
    # For user: question text. For assistant: answer headline only (not full payload).
    content_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    # Serialised answer payload (JSON) — answer contract shape, no full tool results.
    answer_payload_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Verification outcome: "verified" | "verified_with_caveats" | "could_not_verify"
    verification_label: Mapped[str | None] = mapped_column(String(30), nullable=True)
    # JSON: [{"check": "C1", "outcome": "pass", ...}, ...]
    checks_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Comma-separated tool names used (no params, no results)
    tools_used: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Token usage
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    latency_ms: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    session: Mapped["AsstSession"] = relationship("AsstSession", back_populates="messages")
    feedback: Mapped[list["AsstFeedback"]] = relationship(
        "AsstFeedback", back_populates="message", cascade="all, delete-orphan"
    )


class AsstFeedback(Base):
    """Thumbs up/down + optional free-text reason from the user."""
    __tablename__ = "asst_feedback"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_new_uuid)
    message_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("asst_message.id", ondelete="CASCADE"), nullable=False
    )
    rating: Mapped[int] = mapped_column(Integer, nullable=False)  # 1=up, -1=down
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, nullable=False
    )

    message: Mapped["AsstMessage"] = relationship("AsstMessage", back_populates="feedback")
