from dataclasses import dataclass
from datetime import datetime
from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.core.config import get_settings


class MeetingBaaSError(Exception):
    pass


class MeetingBaaSTransientError(MeetingBaaSError):
    pass


@dataclass(frozen=True)
class MeetingBaaSBot:
    bot_id: str


@dataclass(frozen=True)
class MeetingBaaSBotStatus:
    bot_id: str
    status: str | None
    transcription_status: str | None = None
    updated_at: str | None = None


@dataclass(frozen=True)
class MeetingBaaSRecordingData:
    audio_url: str
    duration_seconds: float | None


class MeetingBaaSClient:
    def __init__(
        self,
        api_key: str,
        base_url: str,
        timeout_seconds: float = 10.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.transport = transport

    @property
    def _headers(self) -> dict[str, str]:
        return {
            "Content-Type": "application/json",
            "x-meeting-baas-api-key": self.api_key,
        }

    @retry(
        retry=retry_if_exception_type(MeetingBaaSTransientError),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def create_bot(self, meeting_url: str, title: str | None = None) -> MeetingBaaSBot:
        settings = get_settings()
        webhook_base_url = settings.webhook_base_url.rstrip("/")
        callback_secret = settings.meeting_baas_webhook_secret or settings.meeting_baas_api_key
        payload: dict[str, Any] = {
            "meeting_url": meeting_url,
            "bot_name": title or "MOM Meeting Bot",
            "recording_mode": "speaker_view",
            "transcription_enabled": False,
            "callback_enabled": True,
            "callback_config": {
                "url": f"{webhook_base_url}/api/webhooks/meetingbaas",
                "method": "POST",
                "secret": callback_secret,
            },
        }

        response = await self._request(
            "POST",
            "/v2/bots",
            json=payload,
            transient_message="Meeting BaaS bot creation is temporarily unavailable",
            failure_message="Meeting BaaS rejected the meeting request",
        )
        data = _unwrap_data(response)
        bot_id = data.get("bot_id") or data.get("id")
        if not isinstance(bot_id, str) or not bot_id:
            raise MeetingBaaSError("Meeting BaaS response did not include a bot id")

        return MeetingBaaSBot(bot_id=bot_id)

    @retry(
        retry=retry_if_exception_type(MeetingBaaSTransientError),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def get_bot_status(self, bot_id: str) -> MeetingBaaSBotStatus:
        response = await self._request(
            "GET",
            f"/v2/bots/{bot_id}/status",
            transient_message="Meeting BaaS bot status lookup is temporarily unavailable",
            failure_message="Meeting BaaS rejected the bot status lookup",
        )
        data = _unwrap_data(response)

        response_bot_id = data.get("bot_id") if isinstance(data.get("bot_id"), str) else bot_id
        status = data.get("status") if isinstance(data.get("status"), str) else None
        transcription_status = (
            data.get("transcription_status")
            if isinstance(data.get("transcription_status"), str)
            else None
        )
        updated_at = data.get("updated_at") if isinstance(data.get("updated_at"), str) else None

        return MeetingBaaSBotStatus(
            bot_id=response_bot_id,
            status=status,
            transcription_status=transcription_status,
            updated_at=updated_at,
        )

    @retry(
        retry=retry_if_exception_type(MeetingBaaSTransientError),
        wait=wait_exponential(multiplier=1, min=1, max=8),
        stop=stop_after_attempt(3),
        reraise=True,
    )
    async def get_recording_data(self, bot_id: str) -> MeetingBaaSRecordingData:
        response = await self._request(
            "GET",
            f"/v2/bots/{bot_id}",
            transient_message="Meeting BaaS recording lookup is temporarily unavailable",
            failure_message="Meeting BaaS rejected the recording lookup",
        )
        data = _unwrap_data(response)

        audio_url = _extract_recording_url(data)
        if audio_url is None:
            raise MeetingBaaSError("Meeting BaaS recording data did not include a recording URL")

        return MeetingBaaSRecordingData(
            audio_url=audio_url,
            duration_seconds=_extract_duration_seconds(data),
        )

    async def get_recording_url(self, bot_id: str) -> str:
        recording_data = await self.get_recording_data(bot_id)
        return recording_data.audio_url

    async def _request(
        self,
        method: str,
        path: str,
        *,
        transient_message: str,
        failure_message: str,
        json: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        try:
            async with httpx.AsyncClient(
                timeout=self.timeout_seconds,
                transport=self.transport,
            ) as client:
                response = await client.request(
                    method,
                    f"{self.base_url}{path}",
                    headers=self._headers,
                    json=json,
                )
        except httpx.TimeoutException as exc:
            raise MeetingBaaSTransientError(f"{transient_message}: request timed out") from exc
        except httpx.TransportError as exc:
            raise MeetingBaaSTransientError(f"{transient_message}: request failed") from exc

        if response.status_code in {408, 429, 500, 502, 503, 504, 507}:
            raise MeetingBaaSTransientError(transient_message)

        if response.status_code >= 400:
            raise MeetingBaaSError(failure_message)

        try:
            data = response.json()
        except ValueError as exc:
            raise MeetingBaaSError("Meeting BaaS response was not valid JSON") from exc

        if not isinstance(data, dict):
            raise MeetingBaaSError("Meeting BaaS response JSON was not an object")
        if data.get("success") is False:
            error_message = data.get("message") or data.get("error") or failure_message
            raise MeetingBaaSError(str(error_message))
        return data


def _unwrap_data(response_data: dict[str, Any]) -> dict[str, Any]:
    data = response_data.get("data")
    if isinstance(data, dict):
        return data
    return response_data


def _extract_recording_url(bot_data: dict[str, Any]) -> str | None:
    for key in ("audio", "recording", "mp4", "recording_url", "video"):
        value = bot_data.get(key)
        if isinstance(value, str) and value:
            return value
    return None


def _extract_duration_seconds(bot_data: dict[str, Any]) -> float | None:
    for key in ("duration_seconds", "duration", "recording_duration"):
        value = bot_data.get(key)
        if isinstance(value, int | float):
            return float(value)

    started_at = _parse_datetime(bot_data.get("started_at"))
    ended_at = _parse_datetime(bot_data.get("ended_at") or bot_data.get("completed_at"))
    if started_at and ended_at:
        return max(0.0, (ended_at - started_at).total_seconds())

    return None


def _parse_datetime(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


async def get_meetingbaas_client() -> MeetingBaaSClient:
    settings = get_settings()
    return MeetingBaaSClient(
        api_key=settings.meeting_baas_api_key,
        base_url=settings.meeting_baas_base_url,
    )
