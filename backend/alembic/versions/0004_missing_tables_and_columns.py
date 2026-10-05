"""
0004_missing_tables_and_columns.py
Adds all tables and columns that exist in ORM models but were not
included in migrations 0001–0003.

New tables added:
  - segments
  - cases
  - case_conversations
  - review_annotations

New columns added:
  - conversations.provisional_state_json
  - act_initiatives.metric_key
  - act_initiatives.target_value

All operations are additive only — no existing data is modified.
Reversible: downgrade drops the new tables/columns.
"""
from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0004"
down_revision = "5f59b919b761"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── conversations.provisional_state_json ─────────────────────────────────
    with op.batch_alter_table("conversations", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("provisional_state_json", sa.JSON(), nullable=True)
        )

    # ── segments ─────────────────────────────────────────────────────────────
    op.create_table(
        "segments",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "conversation_id",
            sa.String(64),
            sa.ForeignKey("conversations.id"),
            nullable=False,
        ),
        sa.Column("start_turn_id", sa.String(16), nullable=True),
        sa.Column("reason", sa.String(32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_segments_conversation_id", "segments", ["conversation_id"]
    )

    # ── cases ─────────────────────────────────────────────────────────────────
    op.create_table(
        "cases",
        sa.Column("case_id", sa.String(36), primary_key=True),
        sa.Column("external_id", sa.String(128), nullable=True),
        sa.Column("title", sa.String(256), nullable=False, server_default=""),
        sa.Column("status", sa.String(32), nullable=False, server_default="open"),
        sa.Column(
            "created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
    )
    op.create_index("ix_cases_external_id", "cases", ["external_id"])
    op.create_index("ix_cases_status", "cases", ["status"])

    # ── case_conversations ────────────────────────────────────────────────────
    op.create_table(
        "case_conversations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column(
            "case_id",
            sa.String(36),
            sa.ForeignKey("cases.case_id"),
            nullable=False,
        ),
        sa.Column(
            "conversation_id",
            sa.String(36),
            sa.ForeignKey("conversations.id"),
            nullable=False,
        ),
        sa.Column(
            "linked_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
        sa.Column(
            "linked_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True
        ),
        sa.UniqueConstraint(
            "case_id", "conversation_id", name="uq_case_conversation"
        ),
    )
    op.create_index(
        "ix_case_conversations_case_id", "case_conversations", ["case_id"]
    )
    op.create_index(
        "ix_case_conversations_conversation_id",
        "case_conversations",
        ["conversation_id"],
    )

    # ── review_annotations ────────────────────────────────────────────────────
    op.create_table(
        "review_annotations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("review_id", sa.String(36), unique=True, nullable=False),
        sa.Column(
            "conversation_id",
            sa.String(36),
            sa.ForeignKey("conversations.id"),
            nullable=False,
        ),
        sa.Column(
            "reviewer_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True
        ),
        sa.Column("verdict", sa.String(32), nullable=False),
        sa.Column("notes", sa.Text(), nullable=False, server_default=""),
        sa.Column("qa_override_json", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
        ),
    )
    op.create_index(
        "ix_review_annotations_conversation_id",
        "review_annotations",
        ["conversation_id"],
    )
    op.create_index(
        "ix_review_annotations_reviewer_id",
        "review_annotations",
        ["reviewer_id"],
    )
    op.create_index(
        "ix_review_annotations_created_at",
        "review_annotations",
        ["created_at"],
    )

    # ── act_initiatives: metric_key and target_value ──────────────────────────
    with op.batch_alter_table("act_initiatives", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "metric_key", sa.String(64), nullable=False, server_default=""
            )
        )
        batch_op.add_column(
            sa.Column("target_value", sa.Float(), nullable=True)
        )


def downgrade() -> None:
    with op.batch_alter_table("act_initiatives", schema=None) as batch_op:
        batch_op.drop_column("target_value")
        batch_op.drop_column("metric_key")

    op.drop_index("ix_review_annotations_created_at", table_name="review_annotations")
    op.drop_index("ix_review_annotations_reviewer_id", table_name="review_annotations")
    op.drop_index(
        "ix_review_annotations_conversation_id", table_name="review_annotations"
    )
    op.drop_table("review_annotations")

    op.drop_index(
        "ix_case_conversations_conversation_id", table_name="case_conversations"
    )
    op.drop_index("ix_case_conversations_case_id", table_name="case_conversations")
    op.drop_table("case_conversations")

    op.drop_index("ix_cases_status", table_name="cases")
    op.drop_index("ix_cases_external_id", table_name="cases")
    op.drop_table("cases")

    op.drop_index("ix_segments_conversation_id", table_name="segments")
    op.drop_table("segments")

    with op.batch_alter_table("conversations", schema=None) as batch_op:
        batch_op.drop_column("provisional_state_json")
