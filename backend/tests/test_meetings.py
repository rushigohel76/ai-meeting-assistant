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

from app.api.deps import get_current_user  # noqa: E402
from app.api import meetings as meeting_routes  # noqa: E402
from app.main import app  # noqa: E402
from app.models.meeting import Meeting, MeetingStatus  # noqa: E402
from app.models.summary import Summary  # noqa: E402
from app.models.transcript import Transcript  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.meetingbaas import (  # noqa: E402
    MeetingBaaSBot,
    MeetingBaaSError,
    get_meetingbaas_client,
)
from app.services.meetings import get_meeting_repository  # noqa: E402

pytestmark = pytest.mark.anyio


class FakeMeetingRepository:
    def __init__(self) -> None:
        self.meetings: list[Meeting] = []
        self.summaries: dict[uuid.UUID, Summary] = {}
        self.transcripts: dict[uuid.UUID, Transcript] = {}

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
            created_at=datetime.now(UTC),
        )
        self.meetings.append(meeting)
        return meeting

    async def set_bot_joining(self, meeting: Meeting, bot_id: str) -> Meeting:
        meeting.recall_bot_id = bot_id
        meeting.status = MeetingStatus.bot_joining
        return meeting

    async def mark_failed(self, meeting: Meeting) -> Meeting:
        meeting.status = MeetingStatus.failed
        return meeting

    async def list_for_user(
        self,
        user_id: uuid.UUID,
        limit: int,
        offset: int,
    ) -> list[Meeting]:
        user_meetings = [meeting for meeting in self.meetings if meeting.user_id == user_id]
        return user_meetings[offset : offset + limit]

    async def get_by_id(self, meeting_id: uuid.UUID) -> Meeting | None:
        return next(
            (meeting for meeting in self.meetings if meeting.id == meeting_id),
            None,
        )

    async def get_summary_with_transcript(
        self,
        meeting_id: uuid.UUID,
    ) -> tuple[Summary, Transcript] | None:
        summary = self.summaries.get(meeting_id)
        transcript = self.transcripts.get(meeting_id)
        if summary is None or transcript is None:
            return None
        return summary, transcript

    async def get_transcript(self, meeting_id: uuid.UUID) -> Transcript | None:
        return self.transcripts.get(meeting_id)

    def add_meeting(self, user_id: uuid.UUID, title: str) -> Meeting:
        meeting = Meeting(
            id=uuid.uuid4(),
            user_id=user_id,
            meeting_url="https://meet.google.com/abc-defg-hij",
            title=title,
            status=MeetingStatus.bot_joining,
            recall_bot_id=f"bot-{title}",
            created_at=datetime.now(UTC),
        )
        self.meetings.append(meeting)
        return meeting

    def add_summary_and_transcript(self, meeting: Meeting) -> None:
        self.summaries[meeting.id] = Summary(
            id=uuid.uuid4(),
            meeting_id=meeting.id,
            summary_text="A short overview.",
            key_points=["Important point"],
            action_items=[{"task": "Follow up", "owner": "Speaker 1"}],
            decisions=["Ship it"],
            created_at=datetime.now(UTC),
        )
        self.transcripts[meeting.id] = Transcript(
            id=uuid.uuid4(),
            meeting_id=meeting.id,
            raw_transcript_json=[
                {
                    "speaker": "Speaker 1",
                    "text": "Hello.",
                    "start_time": 0.0,
                    "end_time": 1.0,
                }
            ],
            created_at=datetime.now(UTC),
        )


class FakeMeetingBaaSClient:
    def __init__(self, should_fail: bool = False) -> None:
        self.should_fail = should_fail
        self.calls: list[tuple[str, str | None]] = []

    async def create_bot(self, meeting_url: str, title: str | None = None) -> MeetingBaaSBot:
        self.calls.append((meeting_url, title))
        if self.should_fail:
            raise MeetingBaaSError("Meeting BaaS is temporarily unavailable")
        return MeetingBaaSBot(bot_id="meetingbaas-bot-123")


@pytest.fixture()
def current_user() -> User:
    return User(
        id=uuid.uuid4(),
        email="owner@example.com",
        hashed_password="hashed-password",
        full_name="Owner",
    )


@pytest.fixture()
def meeting_repository() -> FakeMeetingRepository:
    return FakeMeetingRepository()


@pytest.fixture()
def meetingbaas_client() -> FakeMeetingBaaSClient:
    return FakeMeetingBaaSClient()


@pytest.fixture(autouse=True)
def override_dependencies(
    current_user: User,
    meeting_repository: FakeMeetingRepository,
    meetingbaas_client: FakeMeetingBaaSClient,
) -> None:
    async def override_current_user() -> User:
        return current_user

    async def override_meeting_repository() -> FakeMeetingRepository:
        return meeting_repository

    async def override_meetingbaas_client() -> FakeMeetingBaaSClient:
        return meetingbaas_client

    app.dependency_overrides[get_current_user] = override_current_user
    app.dependency_overrides[get_meeting_repository] = override_meeting_repository
    app.dependency_overrides[get_meetingbaas_client] = override_meetingbaas_client
    yield
    app.dependency_overrides.clear()


@pytest.fixture()
async def client() -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as test_client:
        yield test_client


async def test_create_meeting_sends_meetingbaas_bot(
    client: httpx.AsyncClient,
    current_user: User,
    meeting_repository: FakeMeetingRepository,
    meetingbaas_client: FakeMeetingBaaSClient,
) -> None:
    response = await client.post(
        "/api/meetings",
        json={
            "meeting_url": "https://meet.google.com/abc-defg-hij",
            "title": "Weekly Sync",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["user_id"] == str(current_user.id)
    assert body["status"] == "bot_joining"
    assert body["recall_bot_id"] == "meetingbaas-bot-123"
    assert meeting_repository.meetings[0].user_id == current_user.id
    assert meetingbaas_client.calls == [("https://meet.google.com/abc-defg-hij", "Weekly Sync")]


async def test_create_meeting_rejects_unsupported_url(client: httpx.AsyncClient) -> None:
    response = await client.post(
        "/api/meetings",
        json={"meeting_url": "https://example.com/not-a-meeting", "title": "Nope"},
    )

    assert response.status_code == 400


async def test_create_meeting_marks_failed_when_meetingbaas_fails(
    client: httpx.AsyncClient,
    meetingbaas_client: FakeMeetingBaaSClient,
    meeting_repository: FakeMeetingRepository,
) -> None:
    meetingbaas_client.should_fail = True

    response = await client.post(
        "/api/meetings",
        json={"meeting_url": "https://zoom.us/j/123456789", "title": "Zoom"},
    )

    assert response.status_code == 502
    assert meeting_repository.meetings[0].status == MeetingStatus.failed


async def test_list_meetings_returns_current_user_only(
    client: httpx.AsyncClient,
    current_user: User,
    meeting_repository: FakeMeetingRepository,
) -> None:
    other_user_id = uuid.uuid4()
    own_meeting = meeting_repository.add_meeting(current_user.id, "Mine")
    meeting_repository.add_meeting(other_user_id, "Not Mine")

    response = await client.get("/api/meetings?limit=10&offset=0")

    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["id"] == str(own_meeting.id)


async def test_get_meeting_blocks_other_users_meetings(
    client: httpx.AsyncClient,
    meeting_repository: FakeMeetingRepository,
) -> None:
    other_meeting = meeting_repository.add_meeting(uuid.uuid4(), "Private")

    response = await client.get(f"/api/meetings/{other_meeting.id}")

    assert response.status_code == 404


async def test_manual_transcription_trigger_requires_owner_and_queues_task(
    client: httpx.AsyncClient,
    current_user: User,
    meeting_repository: FakeMeetingRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    meeting = meeting_repository.add_meeting(current_user.id, "Manual")
    queued_tasks: list[tuple[uuid.UUID, str]] = []

    async def fake_enqueue_transcription_pipeline(
        meeting_id: uuid.UUID,
        event_type: str,
    ) -> None:
        queued_tasks.append((meeting_id, event_type))

    monkeypatch.setattr(
        meeting_routes,
        "enqueue_transcription_pipeline",
        fake_enqueue_transcription_pipeline,
    )

    response = await client.post(f"/api/meetings/{meeting.id}/transcribe")

    assert response.status_code == 202
    assert response.json()["status"] == "queued"
    assert queued_tasks == [(meeting.id, "manual.trigger")]


async def test_get_meeting_summary_returns_completed_summary_and_transcript(
    client: httpx.AsyncClient,
    current_user: User,
    meeting_repository: FakeMeetingRepository,
) -> None:
    meeting = meeting_repository.add_meeting(current_user.id, "Done")
    meeting.status = MeetingStatus.completed
    meeting_repository.add_summary_and_transcript(meeting)

    response = await client.get(f"/api/meetings/{meeting.id}/summary")

    assert response.status_code == 200
    body = response.json()
    assert body["summary"]["summary_text"] == "A short overview."
    assert body["transcript"]["raw_transcript_json"][0]["speaker"] == "Speaker 1"


async def test_get_meeting_summary_requires_completed_status(
    client: httpx.AsyncClient,
    current_user: User,
    meeting_repository: FakeMeetingRepository,
) -> None:
    meeting = meeting_repository.add_meeting(current_user.id, "Not Done")
    meeting.status = MeetingStatus.processing
    meeting_repository.add_summary_and_transcript(meeting)

    response = await client.get(f"/api/meetings/{meeting.id}/summary")

    assert response.status_code == 409


async def test_get_meeting_summary_blocks_other_users(
    client: httpx.AsyncClient,
    meeting_repository: FakeMeetingRepository,
) -> None:
    meeting = meeting_repository.add_meeting(uuid.uuid4(), "Private Summary")
    meeting.status = MeetingStatus.completed
    meeting_repository.add_summary_and_transcript(meeting)

    response = await client.get(f"/api/meetings/{meeting.id}/summary")

    assert response.status_code == 404


async def test_send_meeting_summary_email_sends_to_requested_recipient(
    client: httpx.AsyncClient,
    current_user: User,
    meeting_repository: FakeMeetingRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    meeting = meeting_repository.add_meeting(current_user.id, "Done")
    meeting.status = MeetingStatus.completed
    meeting_repository.add_summary_and_transcript(meeting)
    sent_emails: list[tuple[uuid.UUID, str | None]] = []

    async def fake_send_summary_email(
        meeting_id: uuid.UUID,
        recipient_email: str | None = None,
    ) -> None:
        sent_emails.append((meeting_id, recipient_email))

    monkeypatch.setattr(meeting_routes, "send_summary_email", fake_send_summary_email)

    response = await client.post(
        f"/api/meetings/{meeting.id}/summary/email",
        json={"email": "teammate@example.com"},
    )

    assert response.status_code == 200
    assert response.json() == {"status": "sent"}
    assert sent_emails == [(meeting.id, "teammate@example.com")]


async def test_send_meeting_summary_email_requires_completed_summary(
    client: httpx.AsyncClient,
    current_user: User,
    meeting_repository: FakeMeetingRepository,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    meeting = meeting_repository.add_meeting(current_user.id, "Processing")
    sent_emails: list[tuple[uuid.UUID, str | None]] = []

    async def fake_send_summary_email(
        meeting_id: uuid.UUID,
        recipient_email: str | None = None,
    ) -> None:
        sent_emails.append((meeting_id, recipient_email))

    monkeypatch.setattr(meeting_routes, "send_summary_email", fake_send_summary_email)

    response = await client.post(
        f"/api/meetings/{meeting.id}/summary/email",
        json={"email": "teammate@example.com"},
    )

    assert response.status_code == 409
    assert sent_emails == []


async def test_send_meeting_summary_email_blocks_other_users(
    client: httpx.AsyncClient,
    meeting_repository: FakeMeetingRepository,
) -> None:
    meeting = meeting_repository.add_meeting(uuid.uuid4(), "Private Summary")
    meeting.status = MeetingStatus.completed
    meeting_repository.add_summary_and_transcript(meeting)

    response = await client.post(
        f"/api/meetings/{meeting.id}/summary/email",
        json={"email": "teammate@example.com"},
    )

    assert response.status_code == 404


async def test_get_meeting_transcript_returns_saved_transcript_for_owner(
    client: httpx.AsyncClient,
    current_user: User,
    meeting_repository: FakeMeetingRepository,
) -> None:
    meeting = meeting_repository.add_meeting(current_user.id, "Transcript")
    meeting.status = MeetingStatus.failed
    meeting_repository.add_summary_and_transcript(meeting)

    response = await client.get(f"/api/meetings/{meeting.id}/transcript")

    assert response.status_code == 200
    body = response.json()
    assert body["raw_transcript_json"][0]["text"] == "Hello."


async def test_get_meeting_transcript_blocks_other_users(
    client: httpx.AsyncClient,
    meeting_repository: FakeMeetingRepository,
) -> None:
    meeting = meeting_repository.add_meeting(uuid.uuid4(), "Private Transcript")
    meeting_repository.add_summary_and_transcript(meeting)

    response = await client.get(f"/api/meetings/{meeting.id}/transcript")

    assert response.status_code == 404
