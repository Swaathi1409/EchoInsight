"""Initial schema - all tables.

Revision ID: 0001
Revises: 
Create Date: 2026-10-02

Creates all EchoInsight tables:
  teams, agents, users, conversations, turns, state_events,
  commitments, analyses, qa_results, jobs, audit_log
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # teams
    op.create_table(
        "teams",
        sa.Column("team_id", sa.String(64), primary_key=True),
        sa.Column("display_name", sa.String(128), nullable=False),
        sa.Column("synthetic_assignment", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # agents
    op.create_table(
        "agents",
        sa.Column("agent_id", sa.String(64), primary_key=True),
        sa.Column("display_name", sa.String(128), nullable=False),
        sa.Column("team_id", sa.String(64), sa.ForeignKey("teams.team_id"), nullable=False),
        sa.Column("synthetic_assignment", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # users
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("username", sa.String(64), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(256), nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("agent_id", sa.String(64), sa.ForeignKey("agents.agent_id"), nullable=True),
        sa.Column("team_id", sa.String(64), sa.ForeignKey("teams.team_id"), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_users_username", "users", ["username"])
    op.create_index("ix_users_agent_id", "users", ["agent_id"])
    op.create_index("ix_users_team_id", "users", ["team_id"])

    # conversations
    op.create_table(
        "conversations",
        sa.Column("id", sa.String(64), primary_key=True),
        sa.Column("source_id", sa.String(64), nullable=True),
        sa.Column("agent_id", sa.String(64), sa.ForeignKey("agents.agent_id"), nullable=True),
        sa.Column("team_id", sa.String(64), sa.ForeignKey("teams.team_id"), nullable=True),
        sa.Column("channel", sa.String(32), nullable=False, server_default="call"),
        sa.Column("status", sa.String(32), nullable=False, server_default="created"),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("end_reason", sa.String(32), nullable=True),
        sa.Column("analysis_version", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("synthetic_assignment", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("case_id", sa.String(64), nullable=True),
        sa.Column("resumed_from", sa.String(64), sa.ForeignKey("conversations.id"), nullable=True),
    )
    op.create_index("ix_conversations_source_id", "conversations", ["source_id"])
    op.create_index("ix_conversations_agent_id", "conversations", ["agent_id"])
    op.create_index("ix_conversations_team_id", "conversations", ["team_id"])
    op.create_index("ix_conversations_status", "conversations", ["status"])
    op.create_index("ix_conversations_started_at", "conversations", ["started_at"])

    # turns
    op.create_table(
        "turns",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("turn_id", sa.String(16), nullable=False),
        sa.Column("conversation_id", sa.String(64), sa.ForeignKey("conversations.id"), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("speaker", sa.String(16), nullable=False),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=True),
        sa.Column("text_redacted", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("extraction_status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("conversation_id", "seq", name="uq_turn_conv_seq"),
        sa.UniqueConstraint("conversation_id", "idempotency_key", name="uq_turn_idempotency"),
    )
    op.create_index("ix_turns_conversation_id", "turns", ["conversation_id"])
    op.create_index("ix_turns_turn_id", "turns", ["turn_id"])
    op.create_index("ix_turns_extraction_status", "turns", ["extraction_status"])

    # state_events
    op.create_table(
        "state_events",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("conversation_id", sa.String(64), sa.ForeignKey("conversations.id"), nullable=False),
        sa.Column("turn_id", sa.String(16), nullable=False),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("payload", postgresql.JSON(), nullable=False),
        sa.Column("provisional", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_state_events_conversation_id", "state_events", ["conversation_id"])
    op.create_index("ix_state_events_turn_id", "state_events", ["turn_id"])

    # commitments
    op.create_table(
        "commitments",
        sa.Column("commitment_id", sa.String(64), primary_key=True),
        sa.Column("conversation_id", sa.String(64), sa.ForeignKey("conversations.id"), nullable=False),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("owner", sa.String(128), nullable=True),
        sa.Column("deadline", sa.String(64), nullable=True),
        sa.Column("deadline_flag", sa.String(64), nullable=True),
        sa.Column("status", sa.String(32), nullable=False, server_default="proposed"),
        sa.Column("provisional", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at_turn_id", sa.String(16), nullable=False),
        sa.Column("completed_at_turn_id", sa.String(16), nullable=True),
        sa.Column("carried_over", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("evidence_json", postgresql.JSON(), nullable=False, server_default="[]"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_commitments_conversation_id", "commitments", ["conversation_id"])
    op.create_index("ix_commitments_status", "commitments", ["status"])

    # analyses
    op.create_table(
        "analyses",
        sa.Column("analysis_id", sa.String(64), primary_key=True),
        sa.Column("conversation_id", sa.String(64), sa.ForeignKey("conversations.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("provisional", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("model", sa.String(128), nullable=False),
        sa.Column("prompt_version", sa.String(32), nullable=False),
        sa.Column("policy_version", sa.String(32), nullable=False),
        sa.Column("taxonomy_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("reasons_json", postgresql.JSON(), nullable=False),
        sa.Column("resolution", sa.String(32), nullable=False),
        sa.Column("churn_risk", sa.String(16), nullable=False),
        sa.Column("churn_signals_json", postgresql.JSON(), nullable=False),
        sa.Column("sentiment_trajectory_json", postgresql.JSON(), nullable=False),
        sa.Column("false_resolution", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("false_resolution_reason", sa.Text(), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("conversation_id", "version", name="uq_analysis_conv_version"),
    )
    op.create_index("ix_analyses_conversation_id", "analyses", ["conversation_id"])

    # qa_results
    op.create_table(
        "qa_results",
        sa.Column("qa_result_id", sa.String(64), primary_key=True),
        sa.Column("analysis_id", sa.String(64), sa.ForeignKey("analyses.analysis_id"), nullable=False),
        sa.Column("conversation_id", sa.String(64), sa.ForeignKey("conversations.id"), nullable=False),
        sa.Column("analysis_version", sa.Integer(), nullable=False),
        sa.Column("checklist_version", sa.String(32), nullable=False),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("score_label", sa.String(32), nullable=False),
        sa.Column("coverage", sa.Float(), nullable=False),
        sa.Column("items_applicable", sa.Integer(), nullable=False),
        sa.Column("items_assessed", sa.Integer(), nullable=False),
        sa.Column("items_needs_review", sa.Integer(), nullable=False),
        sa.Column("critical_violation", sa.Boolean(), nullable=False, server_default="false"),
        sa.Column("items_json", postgresql.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_qa_results_conversation_id", "qa_results", ["conversation_id"])
    op.create_index("ix_qa_results_analysis_id", "qa_results", ["analysis_id"])

    # jobs
    op.create_table(
        "jobs",
        sa.Column("job_id", sa.String(64), primary_key=True),
        sa.Column("job_type", sa.String(64), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="queued"),
        sa.Column("conversation_id", sa.String(64), sa.ForeignKey("conversations.id"), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False, unique=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("payload_json", postgresql.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_jobs_status", "jobs", ["status"])
    op.create_index("ix_jobs_conversation_id", "jobs", ["conversation_id"])
    op.create_index("ix_jobs_created_at", "jobs", ["created_at"])

    # audit_log
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("resource_type", sa.String(64), nullable=False),
        sa.Column("resource_id", sa.String(128), nullable=False),
        sa.Column("details_json", postgresql.JSON(), nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_audit_log_user_id", "audit_log", ["user_id"])
    op.create_index("ix_audit_log_resource_type", "audit_log", ["resource_type"])
    op.create_index("ix_audit_log_created_at", "audit_log", ["created_at"])


def downgrade() -> None:
    op.drop_table("audit_log")
    op.drop_table("jobs")
    op.drop_table("qa_results")
    op.drop_table("analyses")
    op.drop_table("commitments")
    op.drop_table("state_events")
    op.drop_table("turns")
    op.drop_table("conversations")
    op.drop_table("users")
    op.drop_table("agents")
    op.drop_table("teams")
