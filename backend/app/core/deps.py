"""
Dependency های مرکزی FastAPI:
- get_current_user: استخراج کاربر از Access Token
- require_permission: Factory برای بررسی RBAC، با پشتیبانی از نقش‌های Site-scoped
- require_superuser: فقط برای مدیر سیستم (is_superuser)

استفاده در هر Endpoint:
    @router.get("/employees")
    async def list_employees(user: User = Depends(require_permission("employees.view"))):
        ...

نکته: require_permission پارامتر جدیدی به نام site_id تعریف نمی‌کند (چون این کار
با Endpoint هایی که site_id را به‌عنوان Path Parameter دارند (مثل /sites/{site_id}/...)
تداخل نام ایجاد می‌کند و باعث AssertionError در FastAPI هنگام Startup می‌شود).
در عوض، وقتی site_scoped=True باشد، مقدار site_id مستقیماً از خودِ Request
(اول از Path Params، بعد از Query Params) خوانده می‌شود.
"""
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.db.session import get_db
from app.models.user import User
from app.repositories.user_repository import UserRepository

# tokenUrl فقط برای مستندات Swagger استفاده می‌شود؛ خود بررسی توکن دستی انجام می‌شود
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


async def get_current_user(
    token: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    ورودی: Bearer Token از هدر Authorization و session دیتابیس.
    توکن را decode می‌کند، نوع access بودن و فعال بودن کاربر را بررسی می‌کند.
    خروجی: شیء User؛ در هر حالت نامعتبر خطای 401 می‌دهد.
    """
    # خطای یکسان برای همه حالت‌های نامعتبر (بدون افشای علت دقیق)
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="احراز هویت نامعتبر یا منقضی‌شده است",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if token is None:
        raise unauthorized

    payload = decode_token(token)
    # فقط Access Token پذیرفته می‌شود، نه Refresh Token
    if payload is None or payload.get("type") != "access":
        raise unauthorized

    user_id = payload.get("sub")
    if user_id is None:
        raise unauthorized

    user = await UserRepository(db).get_by_id(int(user_id))
    # کاربر حذف‌شده یا غیرفعال هم مجاز نیست
    if user is None or not user.is_active:
        raise unauthorized

    return user


def require_permission(permission_code: str, site_scoped: bool = False):
    """
    Dependency factory برای بررسی یک Permission مشخص.

    site_scoped=True: برای Endpoint هایی که site_id را در Path (مثل
    /sites/{site_id}/connection) یا Query (مثل /employees?site_id=2) دارند.
    مقدار site_id از خودِ Request خوانده می‌شود، نه از یک پارامتر تازه —
    تا نقش‌های Site-scoped (مثل "HR فقط سایت ۲") هم لحاظ شوند.
    خروجی: تابع Dependency که کاربر مجاز را برمی‌گرداند یا خطای 403 می‌دهد.
    """

    async def checker(
        request: Request,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        """کاربر جاری را می‌گیرد، مجوز permission_code را بررسی می‌کند و کاربر را برمی‌گرداند."""
        # مدیر سیستم همه مجوزها را دارد
        if current_user.is_superuser:
            return current_user

        # حالت سایت‌محور: فقط نقش‌های سراسری و نقش‌های همان site_id درخواست لحاظ می‌شوند
        if site_scoped:
            raw_site_id = request.path_params.get("site_id") or request.query_params.get("site_id")
            site_id = int(raw_site_id) if raw_site_id is not None else None
            codes = await UserRepository(db).get_permission_codes(current_user.id, site_id=site_id)
        else:
            # Endpoint غیرسایت‌محور: مجوز از هر انتصاب نقشی (سراسری یا هر سایتی) پذیرفته می‌شود
            codes = await UserRepository(db).get_all_permission_codes(current_user.id)

        # نبود مجوز در مجموعه کدهای کاربر یعنی 403
        if permission_code not in codes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"دسترسی لازم برای این عملیات را ندارید: {permission_code}",
            )
        return current_user

    return checker


async def require_superuser(current_user: User = Depends(get_current_user)) -> User:
    """
    فقط کاربر با is_superuser=True را می‌پذیرد و برمی‌گرداند؛ در غیر این صورت 403.
    برخلاف require_permission هیچ Permission Code ای را قبول نمی‌کند؛ برای تنظیماتی
    که نباید از طریق RBAC قابل‌اعطا باشند (مثل فهرست کلمات نامناسب گزارش انتقادات).
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="این عملیات فقط برای مدیر سیستم مجاز است")
    return current_user
