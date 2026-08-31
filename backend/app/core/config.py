from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = Field(validation_alias="DATABASE_URL")
    meeting_baas_api_key: str = Field(validation_alias="MEETING_BAAS_API_KEY")
    meeting_baas_base_url: str = Field(
        default="https://api.meetingbaas.com",
        validation_alias="MEETING_BAAS_BASE_URL",
    )
    meeting_baas_webhook_secret: str | None = Field(
        default=None,
        validation_alias="MEETING_BAAS_WEBHOOK_SECRET",
    )
    webhook_base_url: str = Field(validation_alias="WEBHOOK_BASE_URL")
    deepgram_api_key: str = Field(validation_alias="DEEPGRAM_API_KEY")
    deepgram_base_url: str = Field(
        default="https://api.deepgram.com",
        validation_alias="DEEPGRAM_BASE_URL",
    )
    max_transcription_audio_duration_seconds: int = Field(
        default=10_800,
        validation_alias="MAX_TRANSCRIPTION_AUDIO_DURATION_SECONDS",
    )
    anthropic_api_key: str | None = Field(default=None, validation_alias="ANTHROPIC_API_KEY")
    anthropic_base_url: str = Field(
        default="https://api.anthropic.com",
        validation_alias="ANTHROPIC_BASE_URL",
    )
    anthropic_model: str = Field(
        default="claude-sonnet-4-5",
        validation_alias="ANTHROPIC_MODEL",
    )
    anthropic_max_output_tokens: int = Field(
        default=2048,
        validation_alias="ANTHROPIC_MAX_OUTPUT_TOKENS",
    )
    gemini_api_key: str | None = Field(
        default=None,
        validation_alias="GEMINI_API_KEY",
    )
    gemini_base_url: str = Field(
        default="https://generativelanguage.googleapis.com",
        validation_alias="GEMINI_BASE_URL",
    )
    gemini_model: str = Field(
        default="gemini-3.5-flash-lite",
        validation_alias="GEMINI_MODEL",
    )
    gemini_max_output_tokens: int = Field(
        default=2048,
        validation_alias="GEMINI_MAX_OUTPUT_TOKENS",
    )
    max_summary_chunk_chars: int = Field(
        default=60_000,
        validation_alias="MAX_SUMMARY_CHUNK_CHARS",
    )
    jwt_secret_key: str = Field(validation_alias="JWT_SECRET_KEY")
    resend_api_key: str = Field(validation_alias="RESEND_API_KEY")
    resend_base_url: str = Field(
        default="https://api.resend.com",
        validation_alias="RESEND_BASE_URL",
    )
    resend_from_email: str = Field(
        default="MOM <onboarding@resend.dev>",
        validation_alias="RESEND_FROM_EMAIL",
    )
    # SMTP fallback / alternative
    smtp_host: str | None = Field(default=None, validation_alias="SMTP_HOST")
    smtp_port: int = Field(default=587, validation_alias="SMTP_PORT")
    smtp_username: str | None = Field(default=None, validation_alias="SMTP_USERNAME")
    smtp_password: str | None = Field(default=None, validation_alias="SMTP_PASSWORD")
    smtp_use_tls: bool = Field(default=True, validation_alias="SMTP_USE_TLS")
    frontend_base_url: str | None = Field(
        default=None,
        validation_alias="FRONTEND_BASE_URL",
    )
    cors_origins: Annotated[list[str], NoDecode] = Field(validation_alias="CORS_ORIGINS")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("cors_origins", mode="before")
    @classmethod
    def parse_cors_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
