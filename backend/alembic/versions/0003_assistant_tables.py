"""
0003_assistant_tables.py
Adds asst_* tables for the EchoInsight Assistant feature.
Additive only — no existing tables are modified.
Reversible: downgrade drops asst_* tables in reverse order.
"""
import sqlalchemy as sa
from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # asst_settings: one-row runtime toggle for the assistant
    op.create_table(
        "asst_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("model_name", sa.String(100), nullable=False, server_default=""),
        sa.Column("rate_limit_per_user_per_hour", sa.Integer(), nullable=False, server_default="20"),
        sa.Column("max_question_chars", sa.Integer(), nullable=False, server_default="1000"),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )

    # asst_session: one session per user browser session
    op.create_table(
        "asst_session",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "last_active_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("context_json", sa.Text(), nullable=False, server_default="{}"),
    )
    op.create_index("ix_asst_session_user_id", "asst_session", ["user_id"])

    # asst_message: one row per user question or assistant answer
    op.create_table(
        "asst_message",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(36),
            sa.ForeignKey("asst_session.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(10), nullable=False),
        sa.Column("content_text", sa.Text(), nullable=False, server_default=""),
        sa.Column("answer_payload_json", sa.Text(), nullable=True),
        sa.Column("verification_label", sa.String(30), nullable=True),
        sa.Column("checks_json", sa.Text(), nullable=True),
        sa.Column("tools_used", sa.Text(), nullable=True),
        sa.Column("prompt_tokens", sa.Integer(), nullable=True),
        sa.Column("completion_tokens", sa.Integer(), nullable=True),
        sa.Column("latency_ms", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index("ix_asst_message_session_id", "asst_message", ["session_id"])

    # asst_feedback: thumbs up/down per message
    op.create_table(
        "asst_feedback",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "message_id",
            sa.String(36),
            sa.ForeignKey("asst_message.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("rating", sa.Integer(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index("ix_asst_feedback_message_id", "asst_feedback", ["message_id"])


def downgrade() -> None:
    op.drop_index("ix_asst_feedback_message_id", table_name="asst_feedback")
    op.drop_table("asst_feedback")
    op.drop_index("ix_asst_message_session_id", table_name="asst_message")
    op.drop_table("asst_message")
    op.drop_index("ix_asst_session_user_id", table_name="asst_session")
    op.drop_table("asst_session")
    op.drop_table("asst_settings")
