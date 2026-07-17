import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, HttpUrl

from app.models.meeting import MeetingStatus


class MeetingCreate(BaseModel):
    user_id: uuid.UUID
    meeting_url: HttpUrl
    title: str | None = None


class MeetingUpdate(BaseModel):
    meeting_url: HttpUrl | None = None
    title: str | None = None
    status: MeetingStatus | None = None
    recall_bot_id: str | None = None
    started_at: datetime | None = None
    ended_at: datetime | None = None


class MeetingRead(BaseModel):
    id: uuid.UUID
    user_id: uuid.UUID
    meeting_url: str
    title: str | None
    status: MeetingStatus
    recall_bot_id: str | None
    started_at: datetime | None
    ended_at: datetime | None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
