import uuid
import logging

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.exc import IntegrityError

from app.core.rate_limit import limiter
from app.core.security import (
    REFRESH_TOKEN_COOKIE_NAME,
    REFRESH_TOKEN_EXPIRE_DAYS,
    create_access_token,
    create_refresh_token,
    get_token_subject,
    hash_password,
    verify_password,
)
from app.models.user import User
from app.schemas.auth import (
    AccessTokenResponse,
    AuthLoginRequest,
    AuthSignupRequest,
    TokenPair,
    PasswordResetRequest,
    PasswordResetConfirm,
)
from app.services.auth import AuthRepository, get_auth_repository
from app.services.email import send_password_reset_otp
import secrets
from datetime import datetime, timedelta, timezone
from app.core.config import get_settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])

GENERIC_SIGNUP_CONFLICT = "Unable to create account with those credentials"
INVALID_CREDENTIALS = "Invalid credentials"


@router.post("/signup", response_model=TokenPair, status_code=status.HTTP_201_CREATED)
async def signup(
    payload: AuthSignupRequest,
    response: Response,
    auth_repository: AuthRepository = Depends(get_auth_repository),
) -> TokenPair:
    email = payload.email.lower()
    existing_user = await auth_repository.get_user_by_email(email)
    if existing_user is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=GENERIC_SIGNUP_CONFLICT,
        )

    user = User(
        id=uuid.uuid4(),
        email=email,
        hashed_password=hash_password(payload.password),
        full_name=payload.full_name,
    )

    try:
        created_user = await auth_repository.create_user(user)
    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=GENERIC_SIGNUP_CONFLICT,
        ) from None

    return _issue_token_pair(response, created_user.id)


@router.post("/login", response_model=TokenPair)
@limiter.limit("5/15minutes")
async def login(
    request: Request,
    payload: AuthLoginRequest,
    response: Response,
    auth_repository: AuthRepository = Depends(get_auth_repository),
) -> TokenPair:
    user = await auth_repository.get_user_by_email(payload.email.lower())
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=INVALID_CREDENTIALS,
            headers={"WWW-Authenticate": "Bearer"},
        )

    return _issue_token_pair(response, user.id)


@router.post("/refresh", response_model=AccessTokenResponse)
@limiter.limit("10/minute")
async def refresh(
    request: Request,
    auth_repository: AuthRepository = Depends(get_auth_repository),
) -> AccessTokenResponse:
    refresh_token = request.cookies.get(REFRESH_TOKEN_COOKIE_NAME)
    client_ip = request.client.host if request.client else "unknown"
    logger.info("Refresh requested from %s cookie_present=%s", client_ip, bool(refresh_token))
    if refresh_token is None:
        raise _invalid_refresh_token()

    try:
        user_id = get_token_subject(refresh_token, expected_type="refresh")
    except ValueError:
        raise _invalid_refresh_token() from None

    user = await auth_repository.get_user_by_id(user_id)
    if user is None:
        raise _invalid_refresh_token()

    return AccessTokenResponse(access_token=create_access_token(user.id))


def _issue_token_pair(response: Response, user_id: uuid.UUID) -> TokenPair:
    access_token = create_access_token(user_id)
    refresh_token = create_refresh_token(user_id)
    settings = get_settings()
    frontend_base = (settings.frontend_base_url or "").strip()
    frontend_url = frontend_base.lower()
    is_local_frontend = any(
        frontend_url.startswith(prefix)
        for prefix in ("http://localhost", "http://127.0.0.1", "http://[::1]")
    )
    # Local development uses the same-site browser origin (localhost:5173 -> localhost:8000),
    # so a strict cookie is the most reliable setting. HTTPS dev tunnels need cross-site
    # cookies, so allow SameSite=None only there.
    secure_cookie = bool(frontend_base and frontend_url.startswith("https"))
    if is_local_frontend or not frontend_base:
        samesite = "strict"
    elif secure_cookie:
        samesite = "none"
    else:
        samesite = "lax"

    response.set_cookie(
        key=REFRESH_TOKEN_COOKIE_NAME,
        value=refresh_token,
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        httponly=True,
        secure=secure_cookie,
        samesite=samesite,
        path="/api/auth",
    )
    return TokenPair(access_token=access_token, refresh_token=refresh_token)


def _invalid_refresh_token() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired refresh token",
    )


@router.post("/password-reset/request", status_code=status.HTTP_200_OK)
async def password_reset_request(
    payload: PasswordResetRequest,
    auth_repository: AuthRepository = Depends(get_auth_repository),
) -> dict:
    email = payload.email.lower()
    user = await auth_repository.get_user_by_email(email)
    if user:
        # generate 6-digit OTP
        otp = f"{secrets.randbelow(1000000):06d}"
        otp_hash = hash_password(otp)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
        await auth_repository.set_reset_otp_for_user(email, otp_hash, expires_at)
        try:
            await send_password_reset_otp(email, otp)
        except Exception:
            # don't leak send failures to caller
            pass

    return {"detail": "If that email exists, a reset code has been sent"}


@router.post("/password-reset/confirm", status_code=status.HTTP_200_OK)
async def password_reset_confirm(
    payload: PasswordResetConfirm,
    auth_repository: AuthRepository = Depends(get_auth_repository),
) -> dict:
    email = payload.email.lower()
    ok = await auth_repository.verify_reset_otp_and_update_password(
        email, payload.otp, payload.new_password
    )
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired code")
    return {"detail": "Password updated"}
