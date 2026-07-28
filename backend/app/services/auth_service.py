"""
منطق تجاری Authentication: بررسی نام‌کاربری/پسورد، صدور و تمدید توکن.
"""
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    verify_password,
)
from app.models.user import User
from app.repositories.user_repository import UserRepository


class AuthError(Exception):
    """خطای قابل نمایش به کاربر (نام‌کاربری اشتباه، توکن نامعتبر و ...)."""


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = UserRepository(db)

    async def authenticate(self, username: str, password: str) -> User:
        user = await self.repo.get_by_username(username)
        if user is None or not verify_password(password, user.password_hash):
            raise AuthError("نام کاربری یا رمز عبور اشتباه است")
        if not user.is_active:
            raise AuthError("حساب کاربری غیرفعال است")

        user.last_login_at = datetime.now(timezone.utc)
        await self.db.commit()
        return user

    async def login(self, username: str, password: str) -> tuple[str, str]:
        user = await self.authenticate(username, password)
        access_token = create_access_token(subject=str(user.id))
        refresh_token = create_refresh_token(subject=str(user.id))
        return access_token, refresh_token

    async def refresh(self, refresh_token: str) -> str:
        payload = decode_token(refresh_token)
        if payload is None or payload.get("type") != "refresh":
            raise AuthError("رفرش توکن نامعتبر یا منقضی‌شده است")

        user_id = payload.get("sub")
        user = await self.repo.get_by_id(int(user_id)) if user_id else None
        if user is None or not user.is_active:
            raise AuthError("کاربر یافت نشد یا غیرفعال است")

        return create_access_token(subject=str(user.id))
