from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str = Field(validation_alias="DATABASE_URL")
    recall_ai_api_key: str = Field(validation_alias="RECALL_AI_API_KEY")
    deepgram_api_key: str = Field(validation_alias="DEEPGRAM_API_KEY")
    anthropic_api_key: str = Field(validation_alias="ANTHROPIC_API_KEY")
    jwt_secret_key: str = Field(validation_alias="JWT_SECRET_KEY")
    resend_api_key: str = Field(validation_alias="RESEND_API_KEY")
    cors_origins: Annotated[list[str], NoDecode] = Field(validation_alias="CORS_ORIGINS")
    recall_webhook_secret: str = Field(validation_alias="RECALL_WEBHOOK_SECRET")

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
