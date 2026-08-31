import os
import sys

import pytest

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/mom")
os.environ.setdefault("MEETING_BAAS_API_KEY", "test-meeting-baas-key")
os.environ.setdefault("MEETING_BAAS_BASE_URL", "https://api.meetingbaas.com")
os.environ.setdefault("WEBHOOK_BASE_URL", "https://mom-webhooks.ngrok-free.app")
os.environ.setdefault("DEEPGRAM_API_KEY", "test-deepgram-key")
os.environ.setdefault("DEEPGRAM_BASE_URL", "https://api.deepgram.com")
os.environ.setdefault("MAX_TRANSCRIPTION_AUDIO_DURATION_SECONDS", "10800")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-anthropic-key")
os.environ.setdefault("ANTHROPIC_BASE_URL", "https://api.anthropic.com")
os.environ.setdefault("ANTHROPIC_MODEL", "claude-sonnet-4-5")
os.environ.setdefault("ANTHROPIC_MAX_OUTPUT_TOKENS", "2048")
os.environ.setdefault("GEMINI_API_KEY", "test-gemini-key")
os.environ.setdefault("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com")
os.environ.setdefault("GEMINI_MODEL", "gemini-3.5-flash-lite")
os.environ.setdefault("GEMINI_MAX_OUTPUT_TOKENS", "2048")
os.environ.setdefault("MAX_SUMMARY_CHUNK_CHARS", "60000")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-that-is-long-enough-for-tests")
os.environ.setdefault("RESEND_API_KEY", "test-resend-key")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:5173")

sys.path.insert(0, "backend")

from app.services import summarization  # noqa: E402
from app.services.summarization import (  # noqa: E402
    _chunk_text,
    _format_transcript,
    _summarize_text_with_retry,
)

pytestmark = pytest.mark.anyio


def test_format_transcript_creates_speaker_labeled_text() -> None:
    raw_transcript = [
        {"speaker": "Speaker 1", "text": "Hello.", "start_time": 0, "end_time": 1},
        {"speaker": "Speaker 2", "text": "Hi.", "start_time": 1, "end_time": 2},
    ]

    assert _format_transcript(raw_transcript) == "Speaker 1: Hello.\nSpeaker 2: Hi."


def test_chunk_text_splits_long_transcript_on_line_boundaries() -> None:
    chunks = _chunk_text("Speaker 1: one\nSpeaker 2: two\nSpeaker 3: three", 32)

    assert chunks == ["Speaker 1: one\nSpeaker 2: two", "Speaker 3: three"]


async def test_summarize_text_retries_once_when_json_is_malformed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    async def fake_call_claude(**kwargs):
        calls.append(kwargs["system_prompt"])
        if len(calls) == 1:
            return "not json"
        return """
        {
          "summary": "A short summary.",
          "key_points": ["Point"],
          "action_items": [{"task": "Follow up", "owner": "Speaker 1"}],
          "decisions": ["Decision"]
        }
        """

    monkeypatch.setattr(summarization, "_call_claude", fake_call_claude)

    result = await _summarize_text_with_retry(
        text="Speaker 1: Hello",
        api_key="test",
        base_url="https://api.anthropic.com",
        model="claude-sonnet-4-5",
        max_tokens=512,
        mode="meeting",
    )

    assert result.summary == "A short summary."
    assert len(calls) == 2
    assert "Your previous response was not valid JSON" in calls[1]


async def test_summarize_text_uses_gemini_provider_when_requested(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    async def fake_call_gemini(**kwargs):
        calls.append(kwargs["system_prompt"])
        return """
        {
          "summary": "A Gemini summary.",
          "key_points": ["Point"],
          "action_items": [{"task": "Follow up", "owner": "Speaker 1"}],
          "decisions": ["Decision"]
        }
        """

    monkeypatch.setattr(summarization, "_call_gemini", fake_call_gemini)

    result = await _summarize_text_with_retry(
        text="Speaker 1: Hello",
        api_key="test",
        base_url="https://generativelanguage.googleapis.com",
        model="gemini-3.5-flash-lite",
        max_tokens=512,
        mode="meeting",
        provider="gemini",
    )

    assert result.summary == "A Gemini summary."
    assert calls == [summarization.SUMMARY_SYSTEM_PROMPT]
