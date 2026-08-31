import logging
import uuid
from dataclasses import dataclass
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models.meeting import MeetingStatus
from app.models.transcript import Transcript
from app.services.meetingbaas import MeetingBaaSClient
from app.services.meetings import MeetingRepository
from app.services.summarization import enqueue_summarization_pipeline

logger = logging.getLogger(__name__)


async def enqueue_transcription_pipeline(meeting_id: uuid.UUID, event_type: str) -> None:
    try:
        await transcribe_meeting(meeting_id=meeting_id)
    except Exception:
        logger.exception(
            "Transcription pipeline failed",
            extra={"meeting_id": str(meeting_id), "event_type": event_type},
        )
        await _mark_meeting_failed(meeting_id)


@dataclass(frozen=True)
class TranscriptSegment:
    speaker: str
    text: str
    start_time: float
    end_time: float


class TranscriptionError(Exception):
    pass


async def transcribe_meeting(meeting_id: uuid.UUID) -> list[dict[str, Any]]:
    settings = get_settings()

    async with AsyncSessionLocal() as db:
        meeting_repository = MeetingRepository(db)
        meeting = await meeting_repository.get_by_id(meeting_id)
        if meeting is None:
            raise TranscriptionError("Meeting not found")

        try:
            if not meeting.recall_bot_id:
                raise TranscriptionError("Meeting does not have a Meeting BaaS bot id")

            meetingbaas_client = MeetingBaaSClient(
                api_key=settings.meeting_baas_api_key,
                base_url=settings.meeting_baas_base_url,
            )
            recording_data = await meetingbaas_client.get_recording_data(meeting.recall_bot_id)
            if (
                recording_data.duration_seconds is not None
                and recording_data.duration_seconds
                > settings.max_transcription_audio_duration_seconds
            ):
                raise TranscriptionError("Meeting audio exceeds the configured transcription limit")

            deepgram_response = await _send_to_deepgram(
                audio_url=recording_data.audio_url,
                api_key=settings.deepgram_api_key,
                base_url=settings.deepgram_base_url,
            )
            transcript = _parse_deepgram_response(deepgram_response)
            await _save_transcript(db, meeting_id, transcript)
        except Exception:
            await meeting_repository.update_status(meeting, MeetingStatus.failed)
            logger.exception(
                "Meeting transcription failed",
                extra={"meeting_id": str(meeting_id), "bot_id": meeting.recall_bot_id},
            )
            raise

    await enqueue_summarization_pipeline(meeting_id)
    return transcript


async def _send_to_deepgram(
    *,
    audio_url: str,
    api_key: str,
    base_url: str,
) -> dict[str, Any]:
    headers = {
        "Authorization": f"Token {api_key}",
        "Content-Type": "application/json",
    }
    params = {
        "model": "nova-3",
        "diarize": "true",
        "utterances": "true",
        "punctuate": "true",
        "smart_format": "true",
    }

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{base_url.rstrip('/')}/v1/listen",
                headers=headers,
                params=params,
                json={"url": audio_url},
            )
    except httpx.TimeoutException as exc:
        raise TranscriptionError("Deepgram transcription timed out") from exc
    except httpx.TransportError as exc:
        raise TranscriptionError("Deepgram transcription request failed") from exc

    if response.status_code >= 400:
        raise TranscriptionError("Deepgram transcription request was rejected")

    return response.json()


def _parse_deepgram_response(response_data: dict[str, Any]) -> list[dict[str, Any]]:
    utterances = response_data.get("results", {}).get("utterances")
    if isinstance(utterances, list) and utterances:
        return [
            segment
            for segment in (_segment_from_utterance(utterance) for utterance in utterances)
            if segment is not None
        ]

    channels = response_data.get("results", {}).get("channels", [])
    if not channels or not isinstance(channels[0], dict):
        return []

    alternatives = channels[0].get("alternatives", [{}])
    words = alternatives[0].get("words", []) if alternatives else []
    return _segments_from_words(words)


def _segment_from_utterance(utterance: Any) -> dict[str, Any] | None:
    if not isinstance(utterance, dict):
        return None

    transcript = utterance.get("transcript")
    if not isinstance(transcript, str) or not transcript.strip():
        return None

    speaker_number = utterance.get("speaker")
    speaker = _format_speaker(speaker_number)
    return {
        "speaker": speaker,
        "text": transcript.strip(),
        "start_time": _as_float(utterance.get("start")),
        "end_time": _as_float(utterance.get("end")),
    }


def _segments_from_words(words: Any) -> list[dict[str, Any]]:
    if not isinstance(words, list):
        return []

    segments: list[dict[str, Any]] = []
    current_speaker: int | str | None = None
    current_words: list[str] = []
    start_time = 0.0
    end_time = 0.0

    for word in words:
        if not isinstance(word, dict):
            continue

        speaker = word.get("speaker", 0)
        text = word.get("punctuated_word") or word.get("word")
        if not isinstance(text, str):
            continue

        if current_words and speaker != current_speaker:
            segments.append(
                {
                    "speaker": _format_speaker(current_speaker),
                    "text": " ".join(current_words),
                    "start_time": start_time,
                    "end_time": end_time,
                }
            )
            current_words = []
            start_time = _as_float(word.get("start"))

        if not current_words:
            start_time = _as_float(word.get("start"))

        current_speaker = speaker
        current_words.append(text)
        end_time = _as_float(word.get("end"), default=start_time)

    if current_words:
        segments.append(
            {
                "speaker": _format_speaker(current_speaker),
                "text": " ".join(current_words),
                "start_time": start_time,
                "end_time": end_time,
            }
        )

    return segments


def _format_speaker(speaker_number: int | str | None) -> str:
    try:
        return f"Speaker {int(speaker_number) + 1}"
    except (TypeError, ValueError):
        return "Speaker 1"


def _as_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


async def _save_transcript(
    db: AsyncSession,
    meeting_id: uuid.UUID,
    transcript: list[dict[str, Any]],
) -> None:
    result = await db.execute(select(Transcript).where(Transcript.meeting_id == meeting_id))
    existing_transcript = result.scalar_one_or_none()
    if existing_transcript is None:
        db.add(
            Transcript(
                id=uuid.uuid4(),
                meeting_id=meeting_id,
                raw_transcript_json=transcript,
            )
        )
    else:
        existing_transcript.raw_transcript_json = transcript

    await db.commit()


async def run_transcription_pipeline(meeting_id: uuid.UUID, event_type: str) -> None:
    logger.info(
        "Transcription pipeline queued",
        extra={"meeting_id": str(meeting_id), "event_type": event_type},
    )


async def _mark_meeting_failed(meeting_id: uuid.UUID) -> None:
    async with AsyncSessionLocal() as db:
        repository = MeetingRepository(db)
        meeting = await repository.get_by_id(meeting_id)
        if meeting is not None:
            await repository.update_status(meeting, MeetingStatus.failed)
