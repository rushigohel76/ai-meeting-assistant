"""add user reset otp fields

Revision ID: 20260819_0002
Revises: 20260715_0001
Create Date: 2026-08-19 00:00:00.000000
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260819_0002"
down_revision = "20260715_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("reset_otp_hash", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "users",
        sa.Column("reset_otp_expires_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "reset_otp_expires_at")
    op.drop_column("users", "reset_otp_hash")
