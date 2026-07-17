from pydantic import BaseModel, EmailStr, Field, field_validator


class AuthSignupRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str | None = None

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, value: str) -> str:
        if not any(character.isdigit() for character in value):
            raise ValueError("Password must contain at least one number")
        return value


class AuthLoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1)


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class AccessTokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
