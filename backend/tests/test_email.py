import os
import sys
import uuid
from datetime import UTC, datetime

import pytest

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/mom")
os.environ.setdefault("MEETING_BAAS_API_KEY", "test-meeting-baas-key")
os.environ.setdefault("WEBHOOK_BASE_URL", "https://mom-webhooks.ngrok-free.app")
os.environ.setdefault("DEEPGRAM_API_KEY", "test-deepgram-key")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-anthropic-key")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-that-is-long-enough-for-tests")
os.environ.setdefault("RESEND_API_KEY", "test-resend-key")
os.environ.setdefault("RESEND_FROM_EMAIL", "MOM <summaries@example.com>")
os.environ.setdefault("FRONTEND_BASE_URL", "http://localhost:5173")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:5173")

sys.path.insert(0, "backend")

from app.services import email as email_service  # noqa: E402
from app.services.email import (  # noqa: E402
    EmailDeliveryError,
    ResendEmailPayload,
    SummaryEmailContext,
    _send_resend_email,
    build_summary_email_payload,
)

pytestmark = pytest.mark.anyio


def test_build_summary_email_payload_includes_summary_sections_without_transcript() -> None:
    context = SummaryEmailContext(
        recipient_email="owner@example.com",
        recipient_name="Rushi",
        meeting_id=uuid.uuid4(),
        meeting_title="Weekly Sync",
        meeting_url="https://meet.google.com/abc-defg-hij",
        created_at=datetime(2026, 8, 14, 10, 30, tzinfo=UTC),
        summary_text="The team reviewed launch readiness.",
        key_points=["Launch checklist is almost done."],
        action_items=[{"task": "Send release notes", "owner": "Speaker 1"}],
        decisions=["Ship on Friday."],
        detail_url="http://localhost:5173/meetings/meeting-id",
    )

    payload = build_summary_email_payload(context)

    assert payload.to_email == "owner@example.com"
    assert payload.subject == "MOM summary: Weekly Sync"
    assert "The team reviewed launch readiness." in payload.text
    assert "Send release notes - Speaker 1" in payload.text
    assert "http://localhost:5173/meetings/meeting-id" in payload.html
    assert "raw_transcript_json" not in payload.text
    assert "Transcript" not in payload.html


async def test_send_resend_email_posts_expected_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict] = []

    class FakeResponse:
        status_code = 202

    class FakeAsyncClient:
        def __init__(self, timeout: float) -> None:
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_) -> None:
            return None

        async def post(self, url: str, headers: dict, json: dict) -> FakeResponse:
            calls.append({"url": url, "headers": headers, "json": json})
            return FakeResponse()

    monkeypatch.setattr(email_service.httpx, "AsyncClient", FakeAsyncClient)

    await _send_resend_email(
        payload=ResendEmailPayload(
            to_email="owner@example.com",
            subject="MOM summary: Weekly Sync",
            html="<p>Ready</p>",
            text="Ready",
        ),
        api_key="resend-key",
        from_email="MOM <summaries@example.com>",
        base_url="https://api.resend.com",
    )

    assert calls == [
        {
            "url": "https://api.resend.com/emails",
            "headers": {
                "Authorization": "Bearer resend-key",
                "Content-Type": "application/json",
            },
            "json": {
                "from": "MOM <summaries@example.com>",
                "to": ["owner@example.com"],
                "subject": "MOM summary: Weekly Sync",
                "html": "<p>Ready</p>",
                "text": "Ready",
            },
        }
    ]


async def test_send_resend_email_raises_generic_error_on_rejection(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeResponse:
        status_code = 400

    class FakeAsyncClient:
        def __init__(self, timeout: float) -> None:
            self.timeout = timeout

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_) -> None:
            return None

        async def post(self, url: str, headers: dict, json: dict) -> FakeResponse:
            return FakeResponse()

    monkeypatch.setattr(email_service.httpx, "AsyncClient", FakeAsyncClient)

    with pytest.raises(EmailDeliveryError, match="rejected"):
        await _send_resend_email(
            payload=ResendEmailPayload(
                to_email="owner@example.com",
                subject="MOM summary",
                html="<p>Ready</p>",
                text="Ready",
            ),
            api_key="resend-key",
            from_email="MOM <summaries@example.com>",
            base_url="https://api.resend.com",
        )
