import json
import logging
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Request, status
from fastapi.responses import JSONResponse

from app.core.config import get_settings
from app.core.webhooks import WebhookSignatureError, verify_meetingbaas_webhook_secret
from app.models.meeting import MeetingStatus
from app.services.meetings import MeetingRepository, get_meeting_repository
from app.services.transcription import enqueue_transcription_pipeline

router = APIRouter(prefix="/api/webhooks", tags=["webhooks"])
logger = logging.getLogger(__name__)

RECORDING_READY_EVENTS = {"bot.completed", "complete", "meeting.completed"}
IDEMPOTENT_STATUSES = {
    MeetingStatus.processing,
    MeetingStatus.completed,
    MeetingStatus.failed,
}


@router.post("/meetingbaas")
async def handle_meetingbaas_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    meeting_repository: MeetingRepository = Depends(get_meeting_repository),
) -> JSONResponse:
    raw_payload = await request.body()
    settings = get_settings()

    try:
        verify_meetingbaas_webhook_secret(
            secret=settings.meeting_baas_webhook_secret or settings.meeting_baas_api_key,
            headers=request.headers,
        )
    except WebhookSignatureError:
        logger.warning("Rejected unverified Meeting BaaS webhook")
        return JSONResponse(
            status_code=status.HTTP_401_UNAUTHORIZED,
            content={"detail": "Invalid webhook signature"},
        )

    try:
        payload = json.loads(raw_payload)
    except json.JSONDecodeError:
        logger.warning("Ignored verified Meeting BaaS webhook with invalid JSON")
        return JSONResponse(content={"status": "ignored"})

    event_type = _extract_event_type(payload)
    bot_id = _extract_bot_id(payload)

    if event_type not in RECORDING_READY_EVENTS or not bot_id:
        logger.info("Ignored Meeting BaaS webhook", extra={"event_type": event_type})
        return JSONResponse(content={"status": "ignored"})

    meeting = await meeting_repository.get_by_bot_id(bot_id)
    if meeting is None:
        logger.warning(
            "Meeting BaaS webhook bot id was not found",
            extra={"event_type": event_type},
        )
        return JSONResponse(content={"status": "ignored"})

    if meeting.status in IDEMPOTENT_STATUSES:
        logger.info(
            "Ignored duplicate Meeting BaaS webhook",
            extra={"meeting_id": str(meeting.id), "event_type": event_type},
        )
        return JSONResponse(content={"status": "already_processed"})

    ended_at = _extract_ended_at(payload)
    meeting = await meeting_repository.mark_processing(meeting, ended_at=ended_at)
    logger.info(
        "Accepted Meeting BaaS complete webhook",
        extra={"meeting_id": str(meeting.id), "event_type": event_type},
    )

    background_tasks.add_task(
        enqueue_transcription_pipeline,
        meeting.id,
        event_type,
    )

    return JSONResponse(content={"status": "accepted"})


def _extract_event_type(payload: dict[str, Any]) -> str | None:
    event_type = payload.get("event") or payload.get("event_type")
    return event_type if isinstance(event_type, str) else None


def _extract_bot_id(payload: dict[str, Any]) -> str | None:
    top_level_bot_id = payload.get("bot_id")
    if isinstance(top_level_bot_id, str):
        return top_level_bot_id

    data = payload.get("data")
    if not isinstance(data, dict):
        return None

    bot_id = data.get("bot_id")
    if isinstance(bot_id, str):
        return bot_id

    bot = data.get("bot")
    if isinstance(bot, dict):
        for key in ("bot_id", "id"):
            bot_id = bot.get(key)
            if isinstance(bot_id, str):
                return bot_id

    return None


def _extract_ended_at(payload: dict[str, Any]) -> datetime:
    data = payload.get("data")
    if isinstance(data, dict):
        for key in ("ended_at", "completed_at", "updated_at", "created_at"):
            timestamp = data.get(key)
            if isinstance(timestamp, str):
                try:
                    return datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                except ValueError:
                    pass

    sent_at = payload.get("sent_at")
    if isinstance(sent_at, str):
        try:
            return datetime.fromisoformat(sent_at.replace("Z", "+00:00"))
        except ValueError:
            pass

    return datetime.now(UTC)
