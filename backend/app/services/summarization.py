import logging
import json
import uuid
from typing import Any

import httpx
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import AsyncSessionLocal
from app.models.meeting import MeetingStatus
from app.models.summary import Summary
from app.models.transcript import Transcript
from app.services.meetings import MeetingRepository
from app.services.notifications import enqueue_summary_email

logger = logging.getLogger(__name__)

SUMMARY_SYSTEM_PROMPT = """
You summarize meeting transcripts for a business productivity app.
Return ONLY valid JSON with this exact shape:
{
  "summary": "2-3 sentence overview",
  "key_points": ["point 1", "point 2"],
  "action_items": [{"task": "...", "owner": "Speaker 2 or name if known"}],
  "decisions": ["decision 1"]
}
Do not wrap the JSON in markdown. Do not include commentary.
""".strip()

STRICT_JSON_PROMPT = """
Your previous response was not valid JSON. Return ONLY valid JSON with exactly these keys:
summary, key_points, action_items, decisions.
No markdown, no prose outside JSON, no trailing commas.
""".strip()


class ActionItemPayload(BaseModel):
    task: str
    owner: str | None = None


class ClaudeSummaryPayload(BaseModel):
    summary: str = Field(min_length=1)
    key_points: list[str]
    action_items: list[ActionItemPayload]
    decisions: list[str]


async def enqueue_summarization_pipeline(meeting_id: uuid.UUID) -> None:
    try:
        await summarize_meeting(meeting_id)
    except Exception:
        logger.exception("Summarization pipeline failed", extra={"meeting_id": str(meeting_id)})


class SummarizationError(Exception):
    pass


async def summarize_meeting(meeting_id: uuid.UUID) -> Summary:
    settings = get_settings()

    async with AsyncSessionLocal() as db:
        meeting_repository = MeetingRepository(db)
        meeting = await meeting_repository.get_by_id(meeting_id)
        if meeting is None:
            raise SummarizationError("Meeting not found")

        try:
            transcript = await _get_transcript(db, meeting_id)
            transcript_text = _format_transcript(transcript.raw_transcript_json)
            chunks = _chunk_text(transcript_text, settings.max_summary_chunk_chars)
            if not chunks:
                raise SummarizationError("Transcript is empty")

            provider = "gemini" if settings.gemini_api_key else "anthropic"
            api_key = settings.gemini_api_key or settings.anthropic_api_key
            base_url = settings.gemini_base_url if settings.gemini_api_key else settings.anthropic_base_url
            model = settings.gemini_model if settings.gemini_api_key else settings.anthropic_model
            max_tokens = (
                settings.gemini_max_output_tokens
                if settings.gemini_api_key
                else settings.anthropic_max_output_tokens
            )
            if not api_key:
                raise SummarizationError("No summarization provider API key configured")

            if len(chunks) == 1:
                summary_payload = await _summarize_text_with_retry(
                    text=chunks[0],
                    api_key=api_key,
                    base_url=base_url,
                    model=model,
                    max_tokens=max_tokens,
                    mode="meeting",
                    provider=provider,
                )
            else:
                chunk_summaries = [
                    await _summarize_text_with_retry(
                        text=chunk,
                        api_key=api_key,
                        base_url=base_url,
                        model=model,
                        max_tokens=max_tokens,
                        mode=f"chunk {index + 1} of {len(chunks)}",
                        provider=provider,
                    )
                    for index, chunk in enumerate(chunks)
                ]
                summary_payload = await _summarize_text_with_retry(
                    text=_format_chunk_summaries(chunk_summaries),
                    api_key=api_key,
                    base_url=base_url,
                    model=model,
                    max_tokens=max_tokens,
                    mode="final merge",
                    provider=provider,
                )

            summary = await _save_summary(db, meeting_id, summary_payload)
            await meeting_repository.update_status(meeting, MeetingStatus.completed)
        except Exception:
            await meeting_repository.update_status(meeting, MeetingStatus.failed)
            logger.exception("Meeting summarization failed", extra={"meeting_id": str(meeting_id)})
            raise

    await enqueue_summary_email(meeting_id)
    return summary


async def _get_transcript(db: AsyncSession, meeting_id: uuid.UUID) -> Transcript:
    result = await db.execute(select(Transcript).where(Transcript.meeting_id == meeting_id))
    transcript = result.scalar_one_or_none()
    if transcript is None:
        raise SummarizationError("Transcript not found")
    return transcript


def _format_transcript(raw_transcript_json: Any) -> str:
    if not isinstance(raw_transcript_json, list):
        raise SummarizationError("Transcript format is invalid")

    lines: list[str] = []
    for segment in raw_transcript_json:
        if not isinstance(segment, dict):
            continue

        speaker = segment.get("speaker")
        text = segment.get("text")
        if not isinstance(speaker, str) or not isinstance(text, str):
            continue
        if text.strip():
            lines.append(f"{speaker}: {text.strip()}")

    return "\n".join(lines)


def _chunk_text(text: str, max_chunk_chars: int) -> list[str]:
    if len(text) <= max_chunk_chars:
        return [text]

    lines = text.splitlines()
    chunks: list[str] = []
    current_chunk: list[str] = []
    current_size = 0

    for line in lines:
        line_size = len(line) + 1
        if current_chunk and current_size + line_size > max_chunk_chars:
            chunks.append("\n".join(current_chunk))
            current_chunk = []
            current_size = 0

        if line_size > max_chunk_chars:
            chunks.extend(
                line[index : index + max_chunk_chars]
                for index in range(0, len(line), max_chunk_chars)
            )
            continue

        current_chunk.append(line)
        current_size += line_size

    if current_chunk:
        chunks.append("\n".join(current_chunk))

    return chunks


async def _summarize_text_with_retry(
    *,
    text: str,
    api_key: str,
    base_url: str,
    model: str,
    max_tokens: int,
    mode: str,
    provider: str = "anthropic",
) -> ClaudeSummaryPayload:
    response_text = await _call_model(
        text=text,
        api_key=api_key,
        base_url=base_url,
        model=model,
        max_tokens=max_tokens,
        system_prompt=SUMMARY_SYSTEM_PROMPT,
        mode=mode,
        provider=provider,
    )

    try:
        return _parse_summary_json(response_text)
    except SummarizationError:
        retry_text = await _call_model(
            text=text,
            api_key=api_key,
            base_url=base_url,
            model=model,
            max_tokens=max_tokens,
            system_prompt=f"{SUMMARY_SYSTEM_PROMPT}\n\n{STRICT_JSON_PROMPT}",
            mode=mode,
            provider=provider,
        )
        return _parse_summary_json(retry_text)


async def _call_model(
    *,
    text: str,
    api_key: str,
    base_url: str,
    model: str,
    max_tokens: int,
    system_prompt: str,
    mode: str,
    provider: str,
) -> str:
    if provider == "gemini":
        return await _call_gemini(
            text=text,
            api_key=api_key,
            base_url=base_url,
            model=model,
            max_tokens=max_tokens,
            system_prompt=system_prompt,
            mode=mode,
        )

    return await _call_claude(
        text=text,
        api_key=api_key,
        base_url=base_url,
        model=model,
        max_tokens=max_tokens,
        system_prompt=system_prompt,
        mode=mode,
    )


async def _call_claude(
    *,
    text: str,
    api_key: str,
    base_url: str,
    model: str,
    max_tokens: int,
    system_prompt: str,
    mode: str,
) -> str:
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system_prompt,
        "messages": [
            {
                "role": "user",
                "content": (
                    f"Summarize this {mode} transcript. "
                    "Do not include transcript quotes unless necessary.\n\n"
                    f"{text}"
                ),
            }
        ],
    }

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                f"{base_url.rstrip('/')}/v1/messages",
                headers=headers,
                json=payload,
            )
    except httpx.TimeoutException as exc:
        raise SummarizationError("Claude summarization timed out") from exc
    except httpx.TransportError as exc:
        raise SummarizationError("Claude summarization request failed") from exc

    if response.status_code >= 400:
        raise SummarizationError("Claude summarization request was rejected")

    data = response.json()
    content = data.get("content")
    if not isinstance(content, list):
        raise SummarizationError("Claude response did not include content")

    text_blocks = [
        block.get("text")
        for block in content
        if isinstance(block, dict) and block.get("type") == "text"
    ]
    combined_text = "\n".join(block for block in text_blocks if isinstance(block, str))
    if not combined_text.strip():
        raise SummarizationError("Claude response was empty")

    return combined_text


async def _call_gemini(
    *,
    text: str,
    api_key: str,
    base_url: str,
    model: str,
    max_tokens: int,
    system_prompt: str,
    mode: str,
) -> str:
    if "/models/" in base_url:
        url = f"{base_url.rstrip('/')}:generateContent?key={api_key}"
    else:
        url = f"{base_url.rstrip('/')}/v1beta/models/{model}:generateContent?key={api_key}"

    payload = {
        "contents": [
            {
                "role": "user",
                "parts": [
                    {
                        "text": (
                            f"Summarize this {mode} transcript. "
                            "Do not include transcript quotes unless necessary.\n\n"
                            f"{text}"
                        )
                    }
                ],
            }
        ],
        "generationConfig": {"maxOutputTokens": max_tokens},
        "systemInstruction": {"parts": [{"text": system_prompt}]},
    }

    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(url, headers={"content-type": "application/json"}, json=payload)
    except httpx.TimeoutException as exc:
        raise SummarizationError("Gemini summarization timed out") from exc
    except httpx.TransportError as exc:
        raise SummarizationError("Gemini summarization request failed") from exc

    if response.status_code >= 400:
        raise SummarizationError("Gemini summarization request was rejected")

    try:
        data = response.json()
    except ValueError as exc:
        raise SummarizationError("Gemini response was not valid JSON") from exc

    candidates = data.get("candidates")
    if not isinstance(candidates, list):
        raise SummarizationError("Gemini response did not include candidates")

    text_blocks: list[str] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        content = candidate.get("content")
        if not isinstance(content, dict):
            continue
        parts = content.get("parts")
        if not isinstance(parts, list):
            continue
        for part in parts:
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                text_blocks.append(part["text"])

    combined_text = "\n".join(text_blocks)
    if not combined_text.strip():
        raise SummarizationError("Gemini response was empty")

    return combined_text


def _parse_summary_json(response_text: str) -> ClaudeSummaryPayload:
    try:
        parsed = _load_json_object(response_text)
        return ClaudeSummaryPayload.model_validate(parsed)
    except (ValueError, ValidationError) as exc:
        raise SummarizationError("Claude response was not valid summary JSON") from exc


def _load_json_object(response_text: str) -> Any:
    try:
        return json.loads(response_text)
    except ValueError:
        start = response_text.find("{")
        end = response_text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise
        return json.loads(response_text[start : end + 1])


def _format_chunk_summaries(chunk_summaries: list[ClaudeSummaryPayload]) -> str:
    return "\n\n".join(summary.model_dump_json() for summary in chunk_summaries)


async def _save_summary(
    db: AsyncSession,
    meeting_id: uuid.UUID,
    summary_payload: ClaudeSummaryPayload,
) -> Summary:
    result = await db.execute(select(Summary).where(Summary.meeting_id == meeting_id))
    summary = result.scalar_one_or_none()
    action_items = [item.model_dump() for item in summary_payload.action_items]

    if summary is None:
        summary = Summary(
            id=uuid.uuid4(),
            meeting_id=meeting_id,
            summary_text=summary_payload.summary,
            key_points=summary_payload.key_points,
            action_items=action_items,
            decisions=summary_payload.decisions,
        )
        db.add(summary)
    else:
        summary.summary_text = summary_payload.summary
        summary.key_points = summary_payload.key_points
        summary.action_items = action_items
        summary.decisions = summary_payload.decisions

    await db.commit()
    await db.refresh(summary)
    return summary
