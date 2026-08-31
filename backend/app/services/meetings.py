import uuid

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.meeting import Meeting, MeetingStatus
from app.models.summary import Summary
from app.models.transcript import Transcript


class MeetingRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def create_pending_meeting(
        self,
        user_id: uuid.UUID,
        meeting_url: str,
        title: str | None,
    ) -> Meeting:
        meeting = Meeting(
            id=uuid.uuid4(),
            user_id=user_id,
            meeting_url=meeting_url,
            title=title,
            status=MeetingStatus.pending,
        )
        self.db.add(meeting)
        await self.db.commit()
        await self.db.refresh(meeting)
        return meeting

    async def set_bot_joining(self, meeting: Meeting, bot_id: str) -> Meeting:
        meeting.recall_bot_id = bot_id
        meeting.status = MeetingStatus.bot_joining
        await self.db.commit()
        await self.db.refresh(meeting)
        return meeting

    async def mark_failed(self, meeting: Meeting) -> Meeting:
        meeting.status = MeetingStatus.failed
        await self.db.commit()
        await self.db.refresh(meeting)
        return meeting

    async def update_status(
        self,
        meeting: Meeting,
        status: MeetingStatus,
    ) -> Meeting:
        meeting.status = status
        await self.db.commit()
        await self.db.refresh(meeting)
        return meeting

    async def mark_processing(
        self,
        meeting: Meeting,
        ended_at,
    ) -> Meeting:
        meeting.status = MeetingStatus.processing
        meeting.ended_at = ended_at
        await self.db.commit()
        await self.db.refresh(meeting)
        return meeting

    async def list_for_user(
        self,
        user_id: uuid.UUID,
        limit: int,
        offset: int,
    ) -> list[Meeting]:
        result = await self.db.execute(
            select(Meeting)
            .where(Meeting.user_id == user_id)
            .order_by(Meeting.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def get_by_id(self, meeting_id: uuid.UUID) -> Meeting | None:
        result = await self.db.execute(select(Meeting).where(Meeting.id == meeting_id))
        return result.scalar_one_or_none()

    async def get_by_bot_id(self, bot_id: str) -> Meeting | None:
        result = await self.db.execute(select(Meeting).where(Meeting.recall_bot_id == bot_id))
        return result.scalar_one_or_none()

    async def get_summary_with_transcript(
        self,
        meeting_id: uuid.UUID,
    ) -> tuple[Summary, Transcript] | None:
        result = await self.db.execute(
            select(Summary, Transcript)
            .join(Transcript, Transcript.meeting_id == Summary.meeting_id)
            .where(Summary.meeting_id == meeting_id)
        )
        row = result.one_or_none()
        if row is None:
            return None
        summary, transcript = row
        return summary, transcript

    async def get_transcript(self, meeting_id: uuid.UUID) -> Transcript | None:
        result = await self.db.execute(
            select(Transcript).where(Transcript.meeting_id == meeting_id)
        )
        return result.scalar_one_or_none()


async def get_meeting_repository(db: AsyncSession = Depends(get_db)) -> MeetingRepository:
    return MeetingRepository(db)
