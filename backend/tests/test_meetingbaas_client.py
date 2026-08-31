import json
import os
from typing import Any

import httpx
import pytest

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/mom")
os.environ.setdefault("MEETING_BAAS_API_KEY", "test-meeting-baas-key")
os.environ.setdefault("MEETING_BAAS_BASE_URL", "https://api.meetingbaas.com")
os.environ.setdefault("WEBHOOK_BASE_URL", "https://mom-webhooks.ngrok-free.app")
os.environ.setdefault("DEEPGRAM_API_KEY", "test-deepgram-key")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-anthropic-key")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-that-is-long-enough-for-tests")
os.environ.setdefault("RESEND_API_KEY", "test-resend-key")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:5173")

from app.services.meetingbaas import MeetingBaaSClient, MeetingBaaSError

pytestmark = pytest.mark.anyio


async def test_create_bot_calls_v2_bots_with_api_key_header() -> None:
    seen_requests: list[dict[str, Any]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        seen_requests.append(
            {
                "method": request.method,
                "path": request.url.path,
                "api_key": request.headers.get("x-meeting-baas-api-key"),
                "payload": json.loads(request.content),
            }
        )
        return httpx.Response(200, json={"success": True, "data": {"bot_id": "bot-123"}})

    client = MeetingBaaSClient(
        api_key="test-key",
        base_url="https://api.meetingbaas.com",
        transport=httpx.MockTransport(handler),
    )

    bot = await client.create_bot(
        meeting_url="https://meet.google.com/abc-defg-hij",
        title="Weekly Sync",
    )

    assert bot.bot_id == "bot-123"
    assert seen_requests == [
        {
            "method": "POST",
            "path": "/v2/bots",
            "api_key": "test-key",
            "payload": {
                "meeting_url": "https://meet.google.com/abc-defg-hij",
                "bot_name": "Weekly Sync",
                "recording_mode": "speaker_view",
                "transcription_enabled": False,
                "callback_enabled": True,
                "callback_config": {
                    "url": "https://mom-webhooks.ngrok-free.app/api/webhooks/meetingbaas",
                    "method": "POST",
                    "secret": "test-meeting-baas-key",
                },
            },
        }
    ]


async def test_get_bot_status_calls_v2_status_endpoint() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/v2/bots/bot-123/status"
        assert request.headers["x-meeting-baas-api-key"] == "test-key"
        return httpx.Response(
            200,
            json={
                "success": True,
                "data": {
                    "bot_id": "bot-123",
                    "status": "in_call_recording",
                    "transcription_status": "disabled",
                    "updated_at": "2026-08-06T10:00:00Z",
                },
            },
        )

    client = MeetingBaaSClient(
        api_key="test-key",
        base_url="https://api.meetingbaas.com",
        transport=httpx.MockTransport(handler),
    )

    status = await client.get_bot_status("bot-123")

    assert status.bot_id == "bot-123"
    assert status.status == "in_call_recording"
    assert status.transcription_status == "disabled"
    assert status.updated_at == "2026-08-06T10:00:00Z"


async def test_get_recording_data_reads_audio_url_from_bot_details() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.method == "GET"
        assert request.url.path == "/v2/bots/bot-123"
        assert request.headers["x-meeting-baas-api-key"] == "test-key"
        return httpx.Response(
            200,
            json={
                "success": True,
                "data": {
                    "bot_id": "bot-123",
                    "audio": "https://example.com/audio.mp3",
                    "duration_seconds": 42,
                },
            },
        )

    client = MeetingBaaSClient(
        api_key="test-key",
        base_url="https://api.meetingbaas.com",
        transport=httpx.MockTransport(handler),
    )

    recording_data = await client.get_recording_data("bot-123")

    assert recording_data.audio_url == "https://example.com/audio.mp3"
    assert recording_data.duration_seconds == 42.0


async def test_api_failures_raise_meetingbaas_error() -> None:
    client = MeetingBaaSClient(
        api_key="test-key",
        base_url="https://api.meetingbaas.com",
        transport=httpx.MockTransport(lambda request: httpx.Response(400, json={"error": "bad"})),
    )

    with pytest.raises(MeetingBaaSError):
        await client.create_bot("https://meet.google.com/abc-defg-hij")


async def test_success_false_response_raises_meetingbaas_error() -> None:
    client = MeetingBaaSClient(
        api_key="test-key",
        base_url="https://api.meetingbaas.com",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json={
                    "success": False,
                    "error": "Insufficient Tokens",
                    "message": "Not enough tokens to create a bot",
                },
            )
        ),
    )

    with pytest.raises(MeetingBaaSError, match="Not enough tokens"):
        await client.create_bot("https://meet.google.com/abc-defg-hij")
