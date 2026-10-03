"""
Alembic migration: 0002_action_layer_tables
Adds all act_* tables for the Action Intelligence Layer.
Additive only — no existing table is modified.
Reversible: downgrade drops all act_* tables in reverse dependency order.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── act_rules_version ────────────────────────────────────────────────────
    op.create_table(
        "act_rules_version",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("kind", sa.String(32), nullable=False),
        sa.Column("version", sa.String(64), nullable=False),
        sa.Column("config_json", sa.JSON, nullable=False),
        sa.Column("active", sa.Boolean, nullable=False, server_default="0"),
        sa.Column("label", sa.String(128), nullable=False, server_default=""),
        sa.Column("created_by", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("kind", "version", name="uq_act_rules_kind_version"),
    )
    op.create_index("ix_act_rules_version_kind_active", "act_rules_version", ["kind", "active"])

    # ── act_settings ─────────────────────────────────────────────────────────
    op.create_table(
        "act_settings",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("enabled", sa.Boolean, nullable=False, server_default="0"),
        sa.Column("as_of_mode", sa.String(16), nullable=False, server_default="dataset_max"),
        sa.Column("manual_as_of", sa.DateTime(timezone=True), nullable=True),
        sa.Column("commitment_due_soon_hours", sa.Integer, nullable=False, server_default="24"),
        sa.Column("high_impact_reasons_json", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    # ── act_items ────────────────────────────────────────────────────────────
    op.create_table(
        "act_items",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("conversation_id", sa.String(64), sa.ForeignKey("conversations.id"), nullable=False),
        sa.Column("analysis_version", sa.Integer, nullable=False),
        sa.Column("risk_rules_version", sa.String(64), nullable=False),
        sa.Column("priority_rules_version", sa.String(64), nullable=False),
        sa.Column("playbook_rules_version", sa.String(64), nullable=False),
        sa.Column("phrase_lists_version", sa.String(64), nullable=False),
        sa.Column("risk_index", sa.Integer, nullable=False),
        sa.Column("risk_band", sa.String(8), nullable=False),
        sa.Column("risk_components_json", sa.JSON, nullable=False),
        sa.Column("impact", sa.String(8), nullable=False),
        sa.Column("urgency", sa.String(8), nullable=False),
        sa.Column("priority", sa.String(4), nullable=False),
        sa.Column("quadrant", sa.String(64), nullable=False),
        sa.Column("intervention_type", sa.String(32), nullable=False),
        sa.Column("intervention_evidence_json", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("evidence_complete", sa.Boolean, nullable=False, server_default="1"),
        sa.Column("evidence_incomplete_reasons_json", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("data_source", sa.String(16), nullable=False, server_default="dataset_pool"),
        sa.Column("status", sa.String(16), nullable=False, server_default="new"),
        sa.Column("assignee_user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("dismissal_reason", sa.Text, nullable=True),
        sa.Column("due_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("current", sa.Boolean, nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    for col in ["conversation_id", "priority", "status", "risk_band", "intervention_type",
                "current", "created_at"]:
        op.create_index(f"ix_act_items_{col}", "act_items", [col])

    # ── act_item_events ──────────────────────────────────────────────────────
    op.create_table(
        "act_item_events",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("item_id", sa.Integer, sa.ForeignKey("act_items.id"), nullable=False),
        sa.Column("event_type", sa.String(32), nullable=False),
        sa.Column("from_status", sa.String(16), nullable=True),
        sa.Column("to_status", sa.String(16), nullable=True),
        sa.Column("actor_user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("notes", sa.Text, nullable=False, server_default=""),
        sa.Column("outcome", sa.String(16), nullable=True),
        sa.Column("payload_json", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_act_item_events_item_id", "act_item_events", ["item_id"])
    op.create_index("ix_act_item_events_created_at", "act_item_events", ["created_at"])

    # ── act_recommendations ──────────────────────────────────────────────────
    op.create_table(
        "act_recommendations",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("item_id", sa.Integer, sa.ForeignKey("act_items.id"), nullable=False),
        sa.Column("rank", sa.Integer, nullable=False),
        sa.Column("action_key", sa.String(64), nullable=False),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("justification", sa.Text, nullable=False),
        sa.Column("signal_refs_json", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("playbook_rule_id", sa.String(64), nullable=False),
        sa.Column("constraint_note", sa.Text, nullable=False, server_default=""),
    )
    op.create_index("ix_act_recommendations_item_id", "act_recommendations", ["item_id"])

    # ── act_drafts ───────────────────────────────────────────────────────────
    op.create_table(
        "act_drafts",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("item_id", sa.Integer, sa.ForeignKey("act_items.id"), nullable=False),
        sa.Column("kind", sa.String(16), nullable=False, server_default="template"),
        sa.Column("content", sa.Text, nullable=False),
        sa.Column("facts_used_json", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("placeholders_json", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("gate_status", sa.String(16), nullable=False, server_default="passed"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_act_drafts_item_id", "act_drafts", ["item_id"])

    # ── act_recurring_issues ─────────────────────────────────────────────────
    op.create_table(
        "act_recurring_issues",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("reason_label", sa.String(128), nullable=False),
        sa.Column("rules_version", sa.String(64), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("window_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("volume", sa.Integer, nullable=False),
        sa.Column("unresolved_rate", sa.Float, nullable=False),
        sa.Column("trend_direction", sa.String(8), nullable=False),
        sa.Column("trend_pct_change", sa.Float, nullable=True),
        sa.Column("prev_window_volume", sa.Integer, nullable=True),
        sa.Column("escalation_share", sa.Float, nullable=False, server_default="0"),
        sa.Column("avg_qa_score", sa.Float, nullable=True),
        sa.Column("repeat_contact_share", sa.Float, nullable=False, server_default="0"),
        sa.Column("example_quotes_json", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("triggered_thresholds_json", sa.JSON, nullable=False, server_default="[]"),
        sa.Column("current", sa.Boolean, nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_act_recurring_issues_reason_label", "act_recurring_issues", ["reason_label"])
    op.create_index("ix_act_recurring_issues_current", "act_recurring_issues", ["current"])

    # ── act_prevention_suggestions ───────────────────────────────────────────
    op.create_table(
        "act_prevention_suggestions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("issue_id", sa.Integer, sa.ForeignKey("act_recurring_issues.id"), nullable=False),
        sa.Column("rules_version", sa.String(64), nullable=False),
        sa.Column("suggestion_text", sa.Text, nullable=False),
        sa.Column("suggested_owner", sa.String(128), nullable=False),
        sa.Column("prevention_rule_id", sa.String(64), nullable=False),
        sa.Column("evidence_json", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_act_prevention_suggestions_issue_id",
                    "act_prevention_suggestions", ["issue_id"])

    # ── act_initiatives ──────────────────────────────────────────────────────
    op.create_table(
        "act_initiatives",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("issue_id", sa.Integer, sa.ForeignKey("act_recurring_issues.id"), nullable=True),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("stage", sa.String(8), nullable=False, server_default="plan"),
        sa.Column("iteration", sa.Integer, nullable=False, server_default="1"),
        sa.Column("demonstration", sa.Boolean, nullable=False, server_default="0"),
        sa.Column("problem_statement", sa.Text, nullable=False, server_default=""),
        sa.Column("root_cause_hypothesis", sa.Text, nullable=False, server_default=""),
        sa.Column("target_metric", sa.String(128), nullable=False, server_default=""),
        sa.Column("target_change", sa.String(128), nullable=False, server_default=""),
        sa.Column("owner", sa.String(128), nullable=False, server_default=""),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("baseline_window_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("baseline_window_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("baseline_metrics_json", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("implementation_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("implementation_description", sa.Text, nullable=False, server_default=""),
        sa.Column("do_owner", sa.String(128), nullable=False, server_default=""),
        sa.Column("do_status", sa.String(32), nullable=False, server_default=""),
        sa.Column("customers_informed", sa.Boolean, nullable=True),
        sa.Column("customers_informed_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("customers_informed_notes", sa.Text, nullable=False, server_default=""),
        sa.Column("check_computed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("check_post_window_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("check_post_window_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("check_post_n", sa.Integer, nullable=True),
        sa.Column("check_sufficient_data", sa.Boolean, nullable=False, server_default="0"),
        sa.Column("check_results_json", sa.JSON, nullable=False, server_default="{}"),
        sa.Column("act_decision", sa.String(16), nullable=True),
        sa.Column("act_notes", sa.Text, nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_act_initiatives_stage", "act_initiatives", ["stage"])
    op.create_index("ix_act_initiatives_demonstration", "act_initiatives", ["demonstration"])

    # ── act_initiative_events ─────────────────────────────────────────────────
    op.create_table(
        "act_initiative_events",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("initiative_id", sa.Integer, sa.ForeignKey("act_initiatives.id"), nullable=False),
        sa.Column("from_stage", sa.String(8), nullable=True),
        sa.Column("to_stage", sa.String(8), nullable=True),
        sa.Column("actor_user_id", sa.Integer, sa.ForeignKey("users.id"), nullable=True),
        sa.Column("notes", sa.Text, nullable=False, server_default=""),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_act_initiative_events_initiative_id",
                    "act_initiative_events", ["initiative_id"])


def downgrade() -> None:
    op.drop_table("act_initiative_events")
    op.drop_table("act_initiatives")
    op.drop_table("act_prevention_suggestions")
    op.drop_table("act_recurring_issues")
    op.drop_table("act_drafts")
    op.drop_table("act_recommendations")
    op.drop_table("act_item_events")
    op.drop_table("act_items")
    op.drop_table("act_settings")
    op.drop_table("act_rules_version")
