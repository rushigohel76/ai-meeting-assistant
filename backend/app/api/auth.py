import uuid

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
from app.schemas.auth import AccessTokenResponse, AuthLoginRequest, AuthSignupRequest, TokenPair
from app.services.auth import AuthRepository, get_auth_repository

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
async def refresh(
    request: Request,
    auth_repository: AuthRepository = Depends(get_auth_repository),
) -> AccessTokenResponse:
    refresh_token = request.cookies.get(REFRESH_TOKEN_COOKIE_NAME)
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
    response.set_cookie(
        key=REFRESH_TOKEN_COOKIE_NAME,
        value=refresh_token,
        max_age=REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        httponly=True,
        secure=True,
        samesite="strict",
        path="/api/auth",
    )
    return TokenPair(access_token=access_token, refresh_token=refresh_token)


def _invalid_refresh_token() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired refresh token",
    )
