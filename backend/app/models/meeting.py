from __future__ import annotations

import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Enum, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.summary import Summary
    from app.models.transcript import Transcript
    from app.models.user import User


class MeetingStatus(str, enum.Enum):
    pending = "pending"
    bot_joining = "bot_joining"
    in_progress = "in_progress"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class Meeting(Base):
    __tablename__ = "meetings"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    meeting_url: Mapped[str] = mapped_column(Text, nullable=False)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[MeetingStatus] = mapped_column(
        Enum(MeetingStatus, name="meeting_status"),
        default=MeetingStatus.pending,
        server_default=MeetingStatus.pending.value,
        nullable=False,
    )
    recall_bot_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )

    user: Mapped[User] = relationship(back_populates="meetings")
    transcript: Mapped[Transcript | None] = relationship(
        back_populates="meeting",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )
    summary: Mapped[Summary | None] = relationship(
        back_populates="meeting",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )
