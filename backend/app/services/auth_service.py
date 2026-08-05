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

    async def authenticate(self, username: str, password: str) -> User | None:
        """
        فقط تلاش برای ورود به‌عنوان کاربر مدیریتی (یوزرنیم/پسورد).
        برخلاف قبل، دیگر در صورت نبود تطبیق خطا نمی‌دهد (None برمی‌گرداند) —
        چون login() یکپارچه در ادامه باید بتواند به‌جایش کد پرسنلی/کد ملی
        پرسنل را هم امتحان کند.
        """
        user = await self.repo.get_by_username(username)
        if user is None or not verify_password(password, user.password_hash):
            return None
        if not user.is_active:
            raise AuthError("حساب کاربری غیرفعال است")

        user.last_login_at = datetime.now(timezone.utc)
        await self.db.commit()
        return user

    async def login(self, identifier: str, credential: str) -> tuple[str, str]:
        """
        فرم ورود یکپارچه: همان دو فیلد، چه برای مدیریت و چه برای پرسنل.
        ابتدا به‌عنوان (یوزرنیم + رمز عبور) کاربر مدیریتی امتحان می‌شود؛
        اگر تطبیق نداشت، به‌عنوان (کد پرسنلی + کد ملی) پرسنل امتحان می‌شود.
        """
        user = await self.authenticate(identifier, credential)

        if user is None:
            employee = await self.repo.find_employee_for_login(identifier, credential)
            if employee is None:
                raise AuthError("اطلاعات ورود اشتباه است")
            user = await self.repo.get_or_create_employee_user(employee)

        access_token = create_access_token(subject=str(user.id))
        refresh_token = create_refresh_token(subject=str(user.id))
        return access_token, refresh_token

    async def refresh(self, refresh_token: str) -> tuple[str, str]:
        """
        تمدید Session — به‌صورت Sliding Window: هر بار که این متد صدا زده شود
        (یعنی کاربر در حال استفاده از برنامه است)، هم Access Token و هم یک
        Refresh Token تازه (با تاریخ انقضای جدید) صادر می‌شود. یعنی تا وقتی
        کاربر حداقل هر REFRESH_TOKEN_EXPIRE_DAYS یک‌بار برنامه را باز کند،
        هرگز به‌صورت خودکار Logout نمی‌شود — فقط با زدن دکمه «خروج» خارج می‌شود.
        """
        payload = decode_token(refresh_token)
        if payload is None or payload.get("type") != "refresh":
            raise AuthError("رفرش توکن نامعتبر یا منقضی‌شده است")

        user_id = payload.get("sub")
        user = await self.repo.get_by_id(int(user_id)) if user_id else None
        if user is None or not user.is_active:
            raise AuthError("کاربر یافت نشد یا غیرفعال است")

        access_token = create_access_token(subject=str(user.id))
        new_refresh_token = create_refresh_token(subject=str(user.id))
        return access_token, new_refresh_token

    async def change_password(self, user: User, current_password: str, new_password: str) -> None:
        if not verify_password(current_password, user.password_hash):
            raise AuthError("رمز عبور فعلی اشتباه است")
        user.password_hash = hash_password(new_password)
        await self.db.commit()
