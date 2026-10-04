"""
backend/action_layer/models.py
SQLAlchemy ORM models for the Action Intelligence Layer.

All tables use the act_ prefix.
All FK references to core tables are read-only (no back-populates into core models).
This module NEVER modifies backend/models.py.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean, DateTime, Float, ForeignKey, Index, Integer,
    String, Text, UniqueConstraint, func,
)
from sqlalchemy import JSON
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from backend.models import Base  # reuse the same declarative base so Alembic sees all tables


# ── Rules versions ────────────────────────────────────────────────────────────

class ActRulesVersion(Base):
    """
    Versioned configuration for every rule set used by the action layer.
    kind: risk | priority | playbook | recurrence | prevention | phrase_lists
    """
    __tablename__ = "act_rules_version"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    config_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    label: Mapped[str] = mapped_column(String(128), default="", nullable=False)  # e.g. "example policy"
    created_by: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("kind", "version", name="uq_act_rules_kind_version"),
        Index("ix_act_rules_version_kind_active", "kind", "active"),
    )


# ── Settings ──────────────────────────────────────────────────────────────────

class ActSettings(Base):
    """Single-row settings table for the action layer runtime toggle and config."""
    __tablename__ = "act_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # as_of_mode: dataset_max | realtime | manual
    as_of_mode: Mapped[str] = mapped_column(String(16), default="dataset_max", nullable=False)
    # manual_as_of used only when as_of_mode=manual
    manual_as_of: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # commitment_due_soon_hours: urgency window
    commitment_due_soon_hours: Mapped[int] = mapped_column(Integer, default=24, nullable=False)
    # high_impact_reasons: JSON list of reason labels
    high_impact_reasons_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


# ── Action Items ──────────────────────────────────────────────────────────────

class ActItem(Base):
    """
    One action item per conversation per rules version (current flag marks latest).
    Derives from stored analysis results only; never triggers new model calls.
    """
    __tablename__ = "act_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    conversation_id: Mapped[str] = mapped_column(
        String(64), ForeignKey("conversations.id"), nullable=False
    )
    analysis_version: Mapped[int] = mapped_column(Integer, nullable=False)
    # risk_rules_version etc. record which rule versions were used
    risk_rules_version: Mapped[str] = mapped_column(String(64), nullable=False)
    priority_rules_version: Mapped[str] = mapped_column(String(64), nullable=False)
    playbook_rules_version: Mapped[str] = mapped_column(String(64), nullable=False)
    phrase_lists_version: Mapped[str] = mapped_column(String(64), nullable=False)

    # Risk Index (1-10, integer)
    risk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    risk_band: Mapped[str] = mapped_column(String(8), nullable=False)  # low|medium|high
    # Full breakdown: list of {component, points, evidence_ref, description}
    risk_components_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False)

    # Priority
    impact: Mapped[str] = mapped_column(String(8), nullable=False)   # high|low
    urgency: Mapped[str] = mapped_column(String(8), nullable=False)  # high|low
    priority: Mapped[str] = mapped_column(String(4), nullable=False)  # P1|P2|P3
    quadrant: Mapped[str] = mapped_column(String(64), nullable=False)  # e.g. "Important, not urgent"

    # Intervention type
    intervention_type: Mapped[str] = mapped_column(String(32), nullable=False)
    # matched phrases and evidence for intervention type
    intervention_evidence_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)

    # Evidence completeness
    evidence_complete: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    evidence_incomplete_reasons_json: Mapped[list[str]] = mapped_column(JSON, default=list)

    # Data source: dataset_pool | live | manual
    data_source: Mapped[str] = mapped_column(String(16), default="dataset_pool", nullable=False)

    # Workflow
    status: Mapped[str] = mapped_column(String(16), default="new", nullable=False)
    # new | claimed | contacted | recovered | lost | dismissed
    assignee_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    dismissal_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Due date (as-of clock based)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Versioning: current=True is the live row; old derives have current=False
    current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    events: Mapped[list[ActItemEvent]] = relationship("ActItemEvent", back_populates="item")
    recommendations: Mapped[list[ActRecommendation]] = relationship(
        "ActRecommendation", back_populates="item"
    )

    __table_args__ = (
        Index("ix_act_items_conversation_id", "conversation_id"),
        Index("ix_act_items_priority", "priority"),
        Index("ix_act_items_status", "status"),
        Index("ix_act_items_risk_band", "risk_band"),
        Index("ix_act_items_intervention_type", "intervention_type"),
        Index("ix_act_items_current", "current"),
        Index("ix_act_items_created_at", "created_at"),
    )


class ActItemEvent(Base):
    """Append-only audit trail of workflow transitions and outcome captures."""
    __tablename__ = "act_item_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    item_id: Mapped[int] = mapped_column(Integer, ForeignKey("act_items.id"), nullable=False)
    event_type: Mapped[str] = mapped_column(String(32), nullable=False)
    # claim | contact_logged | outcome_recorded | dismissed | reopened | reassigned | derived
    from_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    to_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    actor_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    outcome: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # retained | left | no_response | unknown
    payload_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    item: Mapped[ActItem] = relationship("ActItem", back_populates="events")

    __table_args__ = (
        Index("ix_act_item_events_item_id", "item_id"),
        Index("ix_act_item_events_created_at", "created_at"),
    )


class ActRecommendation(Base):
    """Ranked recommended actions for a given ActItem."""
    __tablename__ = "act_recommendations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    item_id: Mapped[int] = mapped_column(Integer, ForeignKey("act_items.id"), nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False)
    action_key: Mapped[str] = mapped_column(String(64), nullable=False)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    justification: Mapped[str] = mapped_column(Text, nullable=False)
    # signal_refs: list of {type, id, quote} evidence references
    signal_refs_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    playbook_rule_id: Mapped[str] = mapped_column(String(64), nullable=False)
    constraint_note: Mapped[str] = mapped_column(Text, default="")

    item: Mapped[ActItem] = relationship("ActItem", back_populates="recommendations")

    __table_args__ = (
        Index("ix_act_recommendations_item_id", "item_id"),
    )


class ActDraft(Base):
    """Follow-up draft for an action item (Tier 1 = deterministic template)."""
    __tablename__ = "act_drafts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    item_id: Mapped[int] = mapped_column(Integer, ForeignKey("act_items.id"), nullable=False)
    kind: Mapped[str] = mapped_column(String(16), default="template", nullable=False)
    # template | model
    content: Mapped[str] = mapped_column(Text, nullable=False)
    facts_used_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    placeholders_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    gate_status: Mapped[str] = mapped_column(String(16), default="passed", nullable=False)
    # passed | needs_human_edit | prohibited_phrase_detected
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_act_drafts_item_id", "item_id"),
    )


# ── Recurring Issues ──────────────────────────────────────────────────────────

class ActRecurringIssue(Base):
    """A detected recurring issue pattern over a call-reason label."""
    __tablename__ = "act_recurring_issues"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    reason_label: Mapped[str] = mapped_column(String(128), nullable=False)
    rules_version: Mapped[str] = mapped_column(String(64), nullable=False)
    window_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    window_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Stats
    volume: Mapped[int] = mapped_column(Integer, nullable=False)
    unresolved_rate: Mapped[float] = mapped_column(Float, nullable=False)
    trend_direction: Mapped[str] = mapped_column(String(8), nullable=False)
    # up | down | flat | insufficient_data
    trend_pct_change: Mapped[float | None] = mapped_column(Float, nullable=True)
    prev_window_volume: Mapped[int | None] = mapped_column(Integer, nullable=True)
    escalation_share: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    avg_qa_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    repeat_contact_share: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    # example_quotes: list of {turn_id, conv_id, quote}
    example_quotes_json: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list)
    triggered_thresholds_json: Mapped[list[str]] = mapped_column(JSON, default=list)
    current: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    initiatives: Mapped[list[ActInitiative]] = relationship("ActInitiative", back_populates="issue")

    __table_args__ = (
        Index("ix_act_recurring_issues_reason_label", "reason_label"),
        Index("ix_act_recurring_issues_current", "current"),
    )


# ── Prevention Suggestions ────────────────────────────────────────────────────

class ActPreventionSuggestion(Base):
    """Evidence-backed prevention suggestion linked to a recurring issue."""
    __tablename__ = "act_prevention_suggestions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    issue_id: Mapped[int] = mapped_column(Integer, ForeignKey("act_recurring_issues.id"), nullable=False)
    rules_version: Mapped[str] = mapped_column(String(64), nullable=False)
    suggestion_text: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_owner: Mapped[str] = mapped_column(String(128), nullable=False)
    prevention_rule_id: Mapped[str] = mapped_column(String(64), nullable=False)
    # label: always "Hypothesis for human validation"
    evidence_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_act_prevention_suggestions_issue_id", "issue_id"),
    )


# ── PDCA Initiatives ──────────────────────────────────────────────────────────

class ActInitiative(Base):
    """
    PDCA improvement initiative linked to a recurring issue.
    Stages: plan | do | check | act
    """
    __tablename__ = "act_initiatives"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    issue_id: Mapped[int] = mapped_column(Integer, ForeignKey("act_recurring_issues.id"), nullable=True)
    title: Mapped[str] = mapped_column(String(256), nullable=False)
    stage: Mapped[str] = mapped_column(String(8), default="plan", nullable=False)
    # plan | do | check | act
    iteration: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    demonstration: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    # PLAN
    problem_statement: Mapped[str] = mapped_column(Text, default="")
    root_cause_hypothesis: Mapped[str] = mapped_column(Text, default="")
    # Structured metric (replaces free-text target_metric/target_change)
    metric_key: Mapped[str] = mapped_column(String(64), default="")
    # e.g. "unresolved_rate" | "weekly_volume" | "escalation_rate" | "custom"
    target_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    # numeric target (e.g. 0.40 for 40%) — None until set
    # Legacy free-text kept for backward compat
    target_metric: Mapped[str] = mapped_column(String(128), default="")
    target_change: Mapped[str] = mapped_column(String(128), default="")
    owner: Mapped[str] = mapped_column(String(128), default="")
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # FROZEN baseline at plan creation
    baseline_window_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    baseline_window_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    baseline_metrics_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)

    # DO
    implementation_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    implementation_description: Mapped[str] = mapped_column(Text, default="")
    do_owner: Mapped[str] = mapped_column(String(128), default="")
    do_status: Mapped[str] = mapped_column(String(32), default="")
    customers_informed: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    customers_informed_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    customers_informed_notes: Mapped[str] = mapped_column(Text, default="")

    # CHECK (computed automatically)
    check_computed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    check_post_window_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    check_post_window_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    check_post_n: Mapped[int | None] = mapped_column(Integer, nullable=True)
    check_sufficient_data: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    check_results_json: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict)
    # check_results: {metric, baseline_value, post_value, change_pct, n_baseline, n_post, caveat}

    # ACT
    act_decision: Mapped[str | None] = mapped_column(String(16), nullable=True)
    # standardize | adjust | abandon
    act_notes: Mapped[str] = mapped_column(Text, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    issue: Mapped[ActRecurringIssue | None] = relationship("ActRecurringIssue", back_populates="initiatives")
    stage_events: Mapped[list[ActInitiativeEvent]] = relationship(
        "ActInitiativeEvent", back_populates="initiative"
    )

    __table_args__ = (
        Index("ix_act_initiatives_stage", "stage"),
        Index("ix_act_initiatives_demonstration", "demonstration"),
    )


class ActInitiativeEvent(Base):
    """Audit trail for initiative stage transitions."""
    __tablename__ = "act_initiative_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    initiative_id: Mapped[int] = mapped_column(Integer, ForeignKey("act_initiatives.id"), nullable=False)
    from_stage: Mapped[str | None] = mapped_column(String(8), nullable=True)
    to_stage: Mapped[str | None] = mapped_column(String(8), nullable=True)
    actor_user_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    initiative: Mapped[ActInitiative] = relationship("ActInitiative", back_populates="stage_events")

    __table_args__ = (
        Index("ix_act_initiative_events_initiative_id", "initiative_id"),
    )
