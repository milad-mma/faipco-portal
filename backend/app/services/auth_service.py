"""
منطق تجاری Authentication: بررسی نام‌کاربری/پسورد، صدور و تمدید توکن.
"""
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
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

    async def employee_login(self, personnel_code: str, national_code: str) -> tuple[str, str]:
        """
        ورود پرسنل با کد پرسنلی به‌جای یوزرنیم و کد ملی به‌جای رمز عبور.
        اولین بار که یک پرسنل با موفقیت وارد شود، یک حساب User به‌صورت
        خودکار برایش ساخته می‌شود (بدون نیاز به دخالت Admin).
        """
        employee = await self.repo.find_employee_for_login(personnel_code, national_code)
        if employee is None:
            raise AuthError("کد پرسنلی یا کد ملی اشتباه است")

        user = await self.repo.get_or_create_employee_user(employee)
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

    async def change_password(self, user: User, current_password: str, new_password: str) -> None:
        if not verify_password(current_password, user.password_hash):
            raise AuthError("رمز عبور فعلی اشتباه است")
        user.password_hash = hash_password(new_password)
        await self.db.commit()
