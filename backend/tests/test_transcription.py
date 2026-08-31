import os
import sys

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/mom")
os.environ.setdefault("MEETING_BAAS_API_KEY", "test-meeting-baas-key")
os.environ.setdefault("MEETING_BAAS_BASE_URL", "https://api.meetingbaas.com")
os.environ.setdefault("WEBHOOK_BASE_URL", "https://mom-webhooks.ngrok-free.app")
os.environ.setdefault("DEEPGRAM_API_KEY", "test-deepgram-key")
os.environ.setdefault("DEEPGRAM_BASE_URL", "https://api.deepgram.com")
os.environ.setdefault("MAX_TRANSCRIPTION_AUDIO_DURATION_SECONDS", "10800")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-anthropic-key")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-that-is-long-enough-for-tests")
os.environ.setdefault("RESEND_API_KEY", "test-resend-key")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:5173")

sys.path.insert(0, "backend")

from app.services.transcription import _parse_deepgram_response  # noqa: E402


def test_parse_deepgram_utterances_into_clean_segments() -> None:
    response = {
        "results": {
            "utterances": [
                {
                    "speaker": 0,
                    "transcript": "Hello there.",
                    "start": 1.25,
                    "end": 2.5,
                },
                {
                    "speaker": 1,
                    "transcript": "Hi!",
                    "start": 3.0,
                    "end": 3.5,
                },
            ]
        }
    }

    assert _parse_deepgram_response(response) == [
        {
            "speaker": "Speaker 1",
            "text": "Hello there.",
            "start_time": 1.25,
            "end_time": 2.5,
        },
        {
            "speaker": "Speaker 2",
            "text": "Hi!",
            "start_time": 3.0,
            "end_time": 3.5,
        },
    ]


def test_parse_deepgram_words_groups_consecutive_speakers() -> None:
    response = {
        "results": {
            "channels": [
                {
                    "alternatives": [
                        {
                            "words": [
                                {
                                    "speaker": 0,
                                    "punctuated_word": "Hello",
                                    "start": 0.0,
                                    "end": 0.4,
                                },
                                {
                                    "speaker": 0,
                                    "punctuated_word": "there.",
                                    "start": 0.4,
                                    "end": 0.8,
                                },
                                {
                                    "speaker": 1,
                                    "punctuated_word": "Yes.",
                                    "start": 1.0,
                                    "end": 1.4,
                                },
                            ]
                        }
                    ]
                }
            ]
        }
    }

    assert _parse_deepgram_response(response) == [
        {
            "speaker": "Speaker 1",
            "text": "Hello there.",
            "start_time": 0.0,
            "end_time": 0.8,
        },
        {
            "speaker": "Speaker 2",
            "text": "Yes.",
            "start_time": 1.0,
            "end_time": 1.4,
        },
    ]
