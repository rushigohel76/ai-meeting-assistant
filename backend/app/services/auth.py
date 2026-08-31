import uuid

from fastapi import Depends
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.user import User
from datetime import datetime
from app.core.security import hash_password, verify_password


class AuthRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_user_by_email(self, email: str) -> User | None:
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def get_user_by_id(self, user_id: uuid.UUID) -> User | None:
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def create_user(self, user: User) -> User:
        self.db.add(user)
        try:
            await self.db.commit()
        except IntegrityError:
            await self.db.rollback()
            raise

        await self.db.refresh(user)
        return user

    async def set_reset_otp_for_user(self, email: str, otp_hash: str, expires_at: datetime) -> bool:
        result = await self.db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user is None:
            return False
        user.reset_otp_hash = otp_hash
        user.reset_otp_expires_at = expires_at
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return True

    async def verify_reset_otp_and_update_password(self, email: str, otp: str, new_password: str) -> bool:
        result = await self.db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()
        if user is None or not user.reset_otp_hash or not user.reset_otp_expires_at:
            return False
        # check expiry
        if datetime.utcnow().replace(tzinfo=None) > user.reset_otp_expires_at.replace(tzinfo=None):
            return False
        if not verify_password(otp, user.reset_otp_hash):
            return False

        user.hashed_password = hash_password(new_password)
        user.reset_otp_hash = None
        user.reset_otp_expires_at = None
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return True


async def get_auth_repository(db: AsyncSession = Depends(get_db)) -> AuthRepository:
    return AuthRepository(db)
