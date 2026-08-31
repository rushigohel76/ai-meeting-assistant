import json
import os
import sys
import uuid
from datetime import UTC, datetime

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

sys.path.insert(0, "backend")

from app.api import webhooks as webhook_routes  # noqa: E402
from app.core.config import get_settings  # noqa: E402
from app.main import app  # noqa: E402
from app.models.meeting import Meeting, MeetingStatus  # noqa: E402
from app.services.meetings import get_meeting_repository  # noqa: E402

pytestmark = pytest.mark.anyio


class FakeMeetingRepository:
    def __init__(self, meeting: Meeting | None = None) -> None:
        self.meeting = meeting
        self.mark_processing_calls = 0

    async def get_by_bot_id(self, bot_id: str) -> Meeting | None:
        if self.meeting and self.meeting.recall_bot_id == bot_id:
            return self.meeting
        return None

    async def mark_processing(self, meeting: Meeting, ended_at: datetime) -> Meeting:
        self.mark_processing_calls += 1
        meeting.status = MeetingStatus.processing
        meeting.ended_at = ended_at
        return meeting


@pytest.fixture()
def meeting() -> Meeting:
    return Meeting(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        meeting_url="https://meet.google.com/abc-defg-hij",
        title="Webhook Test",
        status=MeetingStatus.bot_joining,
        recall_bot_id="meetingbaas-bot-123",
        created_at=datetime.now(UTC),
    )


@pytest.fixture()
def meeting_repository(meeting: Meeting) -> FakeMeetingRepository:
    return FakeMeetingRepository(meeting)


@pytest.fixture()
def queued_tasks(monkeypatch: pytest.MonkeyPatch) -> list[tuple[uuid.UUID, str]]:
    calls: list[tuple[uuid.UUID, str]] = []

    async def fake_enqueue_transcription_pipeline(
        meeting_id: uuid.UUID,
        event_type: str,
    ) -> None:
        calls.append((meeting_id, event_type))

    monkeypatch.setattr(
        webhook_routes,
        "enqueue_transcription_pipeline",
        fake_enqueue_transcription_pipeline,
    )
    return calls


@pytest.fixture(autouse=True)
def override_dependencies(meeting_repository: FakeMeetingRepository) -> None:
    get_settings.cache_clear()

    async def override_meeting_repository() -> FakeMeetingRepository:
        return meeting_repository

    app.dependency_overrides[get_meeting_repository] = override_meeting_repository
    yield
    app.dependency_overrides.clear()
    get_settings.cache_clear()


@pytest.fixture()
async def client() -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as test_client:
        yield test_client


async def test_meetingbaas_webhook_accepts_complete_and_queues_pipeline(
    client: httpx.AsyncClient,
    meeting: Meeting,
    meeting_repository: FakeMeetingRepository,
    queued_tasks: list[tuple[uuid.UUID, str]],
) -> None:
    payload = {
        "event": "complete",
        "data": {
            "bot_id": "meetingbaas-bot-123",
            "ended_at": "2026-07-27T10:00:00Z",
        },
    }

    response = await _post_authenticated_webhook(client, payload)

    assert response.status_code == 200
    assert response.json()["status"] == "accepted"
    assert meeting.status == MeetingStatus.processing
    assert meeting.ended_at == datetime(2026, 7, 27, 10, 0, tzinfo=UTC)
    assert meeting_repository.mark_processing_calls == 1
    assert queued_tasks == [(meeting.id, "complete")]


async def test_meetingbaas_webhook_accepts_v2_bot_completed_callback(
    client: httpx.AsyncClient,
    meeting: Meeting,
    meeting_repository: FakeMeetingRepository,
    queued_tasks: list[tuple[uuid.UUID, str]],
) -> None:
    payload = {
        "event": "bot.completed",
        "data": {
            "bot_id": "meetingbaas-bot-123",
            "meeting_url": "https://meet.google.com/abc-defg-hij",
            "recording": "https://example.com/recording.mp4",
        },
        "sent_at": "2026-08-06T10:00:00Z",
    }

    response = await _post_authenticated_webhook(client, payload)

    assert response.status_code == 200
    assert response.json()["status"] == "accepted"
    assert meeting.status == MeetingStatus.processing
    assert meeting.ended_at == datetime(2026, 8, 6, 10, 0, tzinfo=UTC)
    assert meeting_repository.mark_processing_calls == 1
    assert queued_tasks == [(meeting.id, "bot.completed")]


async def test_meetingbaas_webhook_rejects_invalid_api_key(
    client: httpx.AsyncClient,
    meeting: Meeting,
    queued_tasks: list[tuple[uuid.UUID, str]],
) -> None:
    raw_payload = json.dumps({"event": "complete"}).encode("utf-8")

    response = await client.post(
        "/api/webhooks/meetingbaas",
        content=raw_payload,
        headers={
            "content-type": "application/json",
            "x-meeting-baas-api-key": "invalid",
        },
    )

    assert response.status_code == 401
    assert meeting.status == MeetingStatus.bot_joining
    assert queued_tasks == []


async def test_meetingbaas_webhook_is_idempotent_for_processing_meeting(
    client: httpx.AsyncClient,
    meeting: Meeting,
    meeting_repository: FakeMeetingRepository,
    queued_tasks: list[tuple[uuid.UUID, str]],
) -> None:
    meeting.status = MeetingStatus.processing
    payload = {
        "event": "complete",
        "data": {"bot": {"id": "meetingbaas-bot-123", "metadata": {}}},
    }

    response = await _post_authenticated_webhook(client, payload)

    assert response.status_code == 200
    assert response.json()["status"] == "already_processed"
    assert meeting_repository.mark_processing_calls == 0
    assert queued_tasks == []


async def test_meetingbaas_webhook_unknown_bot_returns_200_without_processing(
    client: httpx.AsyncClient,
    meeting_repository: FakeMeetingRepository,
    queued_tasks: list[tuple[uuid.UUID, str]],
) -> None:
    payload = {
        "event": "complete",
        "data": {"bot": {"id": "unknown-bot", "metadata": {}}},
    }

    response = await _post_authenticated_webhook(client, payload)

    assert response.status_code == 200
    assert response.json()["status"] == "ignored"
    assert meeting_repository.mark_processing_calls == 0
    assert queued_tasks == []


async def _post_authenticated_webhook(
    client: httpx.AsyncClient,
    payload: dict,
) -> httpx.Response:
    raw_payload = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    return await client.post(
        "/api/webhooks/meetingbaas",
        content=raw_payload,
        headers={
            "content-type": "application/json",
            "x-mb-secret": get_settings().meeting_baas_api_key,
        },
    )
