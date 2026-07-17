import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class TranscriptCreate(BaseModel):
    meeting_id: uuid.UUID
    raw_transcript_json: dict[str, Any] | list[Any]


class TranscriptRead(BaseModel):
    id: uuid.UUID
    meeting_id: uuid.UUID
    raw_transcript_json: dict[str, Any] | list[Any]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
