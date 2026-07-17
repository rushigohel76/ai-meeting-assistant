import os
import uuid

import httpx
import pytest
from sqlalchemy.exc import IntegrityError

os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://postgres:postgres@localhost:5432/mom")
os.environ.setdefault("RECALL_AI_API_KEY", "test-recall-key")
os.environ.setdefault("DEEPGRAM_API_KEY", "test-deepgram-key")
os.environ.setdefault("ANTHROPIC_API_KEY", "test-anthropic-key")
os.environ.setdefault("JWT_SECRET_KEY", "test-secret-key-that-is-long-enough-for-tests")
os.environ.setdefault("RESEND_API_KEY", "test-resend-key")
os.environ.setdefault("CORS_ORIGINS", "http://localhost:5173")
os.environ.setdefault("RECALL_WEBHOOK_SECRET", "test-webhook-secret")

from app.api import auth as auth_routes  # noqa: E402
from app.main import app  # noqa: E402
from app.models.user import User  # noqa: E402
from app.services.auth import get_auth_repository  # noqa: E402

pytestmark = pytest.mark.anyio


def fake_hash_password(password: str) -> str:
    return f"hashed:{password}"


def fake_verify_password(plain_password: str, hashed_password: str) -> bool:
    return hashed_password == fake_hash_password(plain_password)


class FakeAuthRepository:
    def __init__(self) -> None:
        self.users_by_email: dict[str, User] = {}
        self.users_by_id: dict[uuid.UUID, User] = {}

    async def get_user_by_email(self, email: str) -> User | None:
        return self.users_by_email.get(email)

    async def get_user_by_id(self, user_id: uuid.UUID) -> User | None:
        return self.users_by_id.get(user_id)

    async def create_user(self, user: User) -> User:
        if user.email in self.users_by_email:
            raise IntegrityError("duplicate user", {}, Exception("duplicate"))

        self.users_by_email[user.email] = user
        self.users_by_id[user.id] = user
        return user

    def add_user(self, email: str, password: str, full_name: str | None = None) -> User:
        user = User(
            id=uuid.uuid4(),
            email=email.lower(),
            hashed_password=fake_hash_password(password),
            full_name=full_name,
        )
        self.users_by_email[user.email] = user
        self.users_by_id[user.id] = user
        return user


@pytest.fixture(autouse=True)
def fast_password_hashing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(auth_routes, "hash_password", fake_hash_password)
    monkeypatch.setattr(auth_routes, "verify_password", fake_verify_password)


@pytest.fixture()
def auth_repository() -> FakeAuthRepository:
    repository = FakeAuthRepository()

    async def override_auth_repository() -> FakeAuthRepository:
        return repository

    app.dependency_overrides[get_auth_repository] = override_auth_repository
    yield repository
    app.dependency_overrides.clear()


@pytest.fixture()
async def client() -> httpx.AsyncClient:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://testserver") as test_client:
        yield test_client


async def test_signup_success(
    client: httpx.AsyncClient,
    auth_repository: FakeAuthRepository,
) -> None:
    response = await client.post(
        "/api/auth/signup",
        json={
            "email": "new@example.com",
            "password": "Password1",
            "full_name": "New User",
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]
    assert body["refresh_token"]

    user = auth_repository.users_by_email["new@example.com"]
    assert user.hashed_password != "Password1"
    assert fake_verify_password("Password1", user.hashed_password)

    set_cookie = response.headers["set-cookie"].lower()
    assert "refresh_token=" in set_cookie
    assert "httponly" in set_cookie
    assert "secure" in set_cookie
    assert "samesite=strict" in set_cookie


async def test_signup_duplicate_email_returns_conflict(
    client: httpx.AsyncClient,
    auth_repository: FakeAuthRepository,
) -> None:
    auth_repository.add_user("taken@example.com", "Password1")

    response = await client.post(
        "/api/auth/signup",
        json={
            "email": "taken@example.com",
            "password": "Password2",
            "full_name": "Duplicate User",
        },
    )

    assert response.status_code == 409
    assert response.json()["detail"] == "Unable to create account with those credentials"


async def test_login_success(
    client: httpx.AsyncClient,
    auth_repository: FakeAuthRepository,
) -> None:
    auth_repository.add_user("login@example.com", "Password1")

    response = await client.post(
        "/api/auth/login",
        json={"email": "login@example.com", "password": "Password1"},
        headers={"x-forwarded-for": "203.0.113.10"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert body["token_type"] == "bearer"
    assert "refresh_token=" in response.headers["set-cookie"].lower()


async def test_login_wrong_password_returns_generic_error(
    client: httpx.AsyncClient,
    auth_repository: FakeAuthRepository,
) -> None:
    auth_repository.add_user("wrong-password@example.com", "Password1")

    response = await client.post(
        "/api/auth/login",
        json={"email": "wrong-password@example.com", "password": "WrongPassword1"},
        headers={"x-forwarded-for": "203.0.113.11"},
    )

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid credentials"


async def test_login_rate_limit_triggers(
    client: httpx.AsyncClient,
    auth_repository: FakeAuthRepository,
) -> None:
    auth_repository.add_user("limited@example.com", "Password1")
    headers = {"x-forwarded-for": "203.0.113.99"}

    for _ in range(5):
        response = await client.post(
            "/api/auth/login",
            json={"email": "limited@example.com", "password": "WrongPassword1"},
            headers=headers,
        )
        assert response.status_code == 401

    response = await client.post(
        "/api/auth/login",
        json={"email": "limited@example.com", "password": "WrongPassword1"},
        headers=headers,
    )

    assert response.status_code == 429
