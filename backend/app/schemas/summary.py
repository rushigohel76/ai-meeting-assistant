import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class ActionItem(BaseModel):
    task: str
    owner: str | None = None


class SummaryCreate(BaseModel):
    meeting_id: uuid.UUID
    summary_text: str
    key_points: list[str]
    action_items: list[ActionItem]
    decisions: list[str]


class SummaryRead(BaseModel):
    id: uuid.UUID
    meeting_id: uuid.UUID
    summary_text: str
    key_points: list[str]
    action_items: list[ActionItem]
    decisions: list[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
