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

from app.core.config import get_settings
from app.core.security import decode_token, is_token_revoked_by_password_change
from app.db.session import get_db
from app.models.user import User
from app.repositories.user_repository import UserRepository

# tokenUrl فقط برای مستندات Swagger استفاده می‌شود؛ خود بررسی توکن دستی انجام می‌شود
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

_API_PREFIX = get_settings().API_V1_PREFIX

# مسیرهایی که کاربرِ ملزم به تعویض رمز (must_change_password) هنوز به آن‌ها دسترسی دارد:
# خواندن پروفایل (برای نمایش دیالوگ اجباری)، خودِ تغییر رمز، تمدید نشست و خروج. بقیه‌ی API 403 می‌گیرد
# تا الزام تعویض رمز فقط به فرانت (MandatoryPasswordChangeGuard) تکیه نکند.
PASSWORD_CHANGE_ALLOWED_PATHS = frozenset(
    f"{_API_PREFIX}{path}" for path in ("/auth/me", "/auth/me/password", "/auth/refresh", "/auth/logout")
)


async def get_current_user(
    request: Request,
    token: str | None = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    ورودی: Request جاری، Bearer Token از هدر Authorization و session دیتابیس.
    توکن را decode می‌کند و بررسی می‌کند: نوع access، صدور پس از آخرین تغییر رمز/خروج (iat)،
    فعال بودن کاربر و پرسنل متصل (Employee.is_active و is_enabled)، و الزام تعویض رمز.
    خروجی: شیء User؛ در هر حالت نامعتبر 401 و برای کاربر ملزم به تعویض رمز (خارج از مسیرهای مجاز) 403
    با detail={"code": "password_change_required", ...} می‌دهد.
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

    # کاربر همراه با وضعیت پرسنل متصل (در یک کوئری) خوانده می‌شود
    user, employee_active = await UserRepository(db).get_by_id_with_employee_status(int(user_id))
    # کاربر حذف‌شده یا غیرفعال هم مجاز نیست
    if user is None or not user.is_active:
        raise unauthorized

    # پرسنلی که در منبع (is_active) یا دستی توسط Admin (is_enabled) غیرفعال شده، حتی با توکن معتبر مجاز نیست
    if employee_active is False:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="حساب غیرفعال است",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # توکن صادرشده پیش از آخرین تغییر رمز/بازنشانی/خروج باطل است (توکن‌های قدیمیِ بدون iat پذیرفته می‌شوند)
    if is_token_revoked_by_password_change(payload, user.password_changed_at):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="نشست منقضی شده؛ دوباره وارد شوید",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # الزام تعویض رمز سمت سرور: فقط فلگ صریح must_change_password (نه ورود پیش‌فرض با کد ملی،
    # که برای پرسنل مجاز است) و فقط خارج از مسیرهای لازم برای خودِ تعویض رمز
    if user.must_change_password and request.url.path.rstrip("/") not in PASSWORD_CHANGE_ALLOWED_PATHS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "password_change_required",
                "message": "برای ادامه باید ابتدا رمز عبور خود را تغییر دهید",
            },
        )

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
