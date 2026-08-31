import re
import uuid
from urllib.parse import urlparse

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status

from app.api.deps import get_current_user
from app.models.meeting import Meeting, MeetingStatus
from app.models.user import User
from app.schemas.meeting import (
    MeetingCreateRequest,
    MeetingRead,
    MeetingSummaryEmailRequest,
    MeetingSummaryEmailResponse,
)
from app.schemas.summary import MeetingSummaryRead
from app.schemas.transcript import TranscriptRead
from app.services.email import EmailDeliveryError, send_summary_email
from app.services.meetings import MeetingRepository, get_meeting_repository
from app.services.meetingbaas import (
    MeetingBaaSClient,
    MeetingBaaSError,
    get_meetingbaas_client,
)
from app.services.transcription import enqueue_transcription_pipeline

router = APIRouter(prefix="/api/meetings", tags=["meetings"])

SUPPORTED_MEETING_PATTERNS = [
    re.compile(r"^https://meet\.google\.com/[a-z]{3}-[a-z]{4}-[a-z]{3}(?:[/?#].*)?$"),
    re.compile(r"^https://([a-z0-9-]+\.)?zoom\.us/(?:j|my|wc/join)/[A-Za-z0-9._-]+(?:[/?#].*)?$"),
    re.compile(r"^https://teams\.microsoft\.com/(?:l/meetup-join|meet)/.+$"),
]


@router.post("", response_model=MeetingRead, status_code=status.HTTP_201_CREATED)
async def create_meeting(
    payload: MeetingCreateRequest,
    current_user: User = Depends(get_current_user),
    meeting_repository: MeetingRepository = Depends(get_meeting_repository),
    meetingbaas_client: MeetingBaaSClient = Depends(get_meetingbaas_client),
) -> Meeting:
    meeting_url = str(payload.meeting_url)
    _validate_supported_meeting_url(meeting_url)

    meeting = await meeting_repository.create_pending_meeting(
        user_id=current_user.id,
        meeting_url=meeting_url,
        title=payload.title,
    )

    try:
        meetingbaas_bot = await meetingbaas_client.create_bot(
            meeting_url=meeting_url,
            title=payload.title,
        )
    except MeetingBaaSError as exc:
        await meeting_repository.mark_failed(meeting)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=str(exc),
        ) from exc

    return await meeting_repository.set_bot_joining(
        meeting=meeting,
        bot_id=meetingbaas_bot.bot_id,
    )


@router.get("", response_model=list[MeetingRead])
async def list_meetings(
    current_user: User = Depends(get_current_user),
    meeting_repository: MeetingRepository = Depends(get_meeting_repository),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[Meeting]:
    return await meeting_repository.list_for_user(
        user_id=current_user.id,
        limit=limit,
        offset=offset,
    )


@router.get("/{meeting_id}", response_model=MeetingRead)
async def get_meeting(
    meeting_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    meeting_repository: MeetingRepository = Depends(get_meeting_repository),
) -> Meeting:
    meeting = await meeting_repository.get_by_id(meeting_id)
    if meeting is None or meeting.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meeting not found",
        )

    return meeting


@router.get("/{meeting_id}/summary", response_model=MeetingSummaryRead)
async def get_meeting_summary(
    meeting_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    meeting_repository: MeetingRepository = Depends(get_meeting_repository),
) -> MeetingSummaryRead:
    meeting = await meeting_repository.get_by_id(meeting_id)
    if meeting is None or meeting.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meeting not found",
        )

    if meeting.status != MeetingStatus.completed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Meeting summary is not ready",
        )

    summary_with_transcript = await meeting_repository.get_summary_with_transcript(meeting.id)
    if summary_with_transcript is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meeting summary not found",
        )

    summary, transcript = summary_with_transcript
    return MeetingSummaryRead(summary=summary, transcript=transcript)


@router.post("/{meeting_id}/summary/email", response_model=MeetingSummaryEmailResponse)
async def send_meeting_summary_email(
    meeting_id: uuid.UUID,
    payload: MeetingSummaryEmailRequest,
    current_user: User = Depends(get_current_user),
    meeting_repository: MeetingRepository = Depends(get_meeting_repository),
) -> MeetingSummaryEmailResponse:
    meeting = await meeting_repository.get_by_id(meeting_id)
    if meeting is None or meeting.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meeting not found",
        )

    if meeting.status != MeetingStatus.completed:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Meeting summary is not ready",
        )

    if await meeting_repository.get_summary_with_transcript(meeting.id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meeting summary not found",
        )

    try:
        await send_summary_email(meeting.id, recipient_email=str(payload.email))
    except EmailDeliveryError as exc:
        # Surface underlying delivery error message to help debugging (not for production)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Unable to send summary email: {str(exc)}",
        ) from exc

    return MeetingSummaryEmailResponse(status="sent")


@router.get("/{meeting_id}/transcript", response_model=TranscriptRead)
async def get_meeting_transcript(
    meeting_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    meeting_repository: MeetingRepository = Depends(get_meeting_repository),
) -> TranscriptRead:
    meeting = await meeting_repository.get_by_id(meeting_id)
    if meeting is None or meeting.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meeting not found",
        )

    transcript = await meeting_repository.get_transcript(meeting.id)
    if transcript is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meeting transcript not found",
        )

    return transcript


@router.post("/{meeting_id}/transcribe", status_code=status.HTTP_202_ACCEPTED)
async def trigger_meeting_transcription(
    meeting_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    meeting_repository: MeetingRepository = Depends(get_meeting_repository),
) -> dict[str, str]:
    meeting = await meeting_repository.get_by_id(meeting_id)
    if meeting is None or meeting.user_id != current_user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Meeting not found",
        )

    background_tasks.add_task(
        enqueue_transcription_pipeline,
        meeting.id,
        "manual.trigger",
    )
    return {"status": "queued"}


def _validate_supported_meeting_url(meeting_url: str) -> None:
    parsed_url = urlparse(meeting_url)
    if parsed_url.scheme != "https" or not parsed_url.netloc:
        raise _unsupported_meeting_url()

    if not any(pattern.match(meeting_url) for pattern in SUPPORTED_MEETING_PATTERNS):
        raise _unsupported_meeting_url()


def _unsupported_meeting_url() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Unsupported meeting URL. Use a Google Meet, Zoom, or Microsoft Teams link.",
    )
