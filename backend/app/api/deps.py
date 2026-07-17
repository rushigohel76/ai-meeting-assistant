from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core.security import get_token_subject
from app.models.user import User
from app.services.auth import AuthRepository, get_auth_repository

bearer_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    auth_repository: AuthRepository = Depends(get_auth_repository),
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise _unauthorized()

    try:
        user_id = get_token_subject(credentials.credentials, expected_type="access")
    except ValueError:
        raise _unauthorized() from None

    user = await auth_repository.get_user_by_id(user_id)
    if user is None:
        raise _unauthorized()

    return user


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
