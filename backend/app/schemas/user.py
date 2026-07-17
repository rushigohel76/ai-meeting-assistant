import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class UserCreate(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str | None = None

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, value: str) -> str:
        if not any(character.isdigit() for character in value):
            raise ValueError("Password must contain at least one number")
        return value


class UserUpdate(BaseModel):
    email: EmailStr | None = None
    password: str | None = Field(default=None, min_length=8)
    full_name: str | None = None


class UserRead(BaseModel):
    id: uuid.UUID
    email: EmailStr
    full_name: str | None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
