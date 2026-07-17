"""create users meetings transcripts summaries

Revision ID: 20260715_0001
Revises:
Create Date: 2026-07-15 01:20:00.000000
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20260715_0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

meeting_status = postgresql.ENUM(
    "pending",
    "bot_joining",
    "in_progress",
    "processing",
    "completed",
    "failed",
    name="meeting_status",
)


def upgrade() -> None:
    bind = op.get_bind()
    meeting_status.create(bind, checkfirst=True)

    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "meetings",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("meeting_url", sa.Text(), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column(
            "status",
            meeting_status,
            server_default="pending",
            nullable=False,
        ),
        sa.Column("recall_bot_id", sa.String(length=255), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ended_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_meetings_user_id", "meetings", ["user_id"], unique=False)

    op.create_table(
        "transcripts",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("meeting_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("raw_transcript_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["meeting_id"], ["meetings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_transcripts_meeting_id",
        "transcripts",
        ["meeting_id"],
        unique=True,
    )

    op.create_table(
        "summaries",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("meeting_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("summary_text", sa.Text(), nullable=False),
        sa.Column("key_points", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("action_items", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("decisions", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["meeting_id"], ["meetings.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_summaries_meeting_id",
        "summaries",
        ["meeting_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_summaries_meeting_id", table_name="summaries")
    op.drop_table("summaries")
    op.drop_index("ix_transcripts_meeting_id", table_name="transcripts")
    op.drop_table("transcripts")
    op.drop_index("ix_meetings_user_id", table_name="meetings")
    op.drop_table("meetings")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
    meeting_status.drop(op.get_bind(), checkfirst=True)
