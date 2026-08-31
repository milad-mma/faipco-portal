"""
Dependency های مرکزی FastAPI:
- get_current_user: استخراج کاربر از Access Token
- require_permission: Factory برای بررسی RBAC، با پشتیبانی از نقش‌های Site-scoped

استفاده در هر Endpoint:
    @router.get("/employees")
    async def list_employees(user: User = Depends(require_permission("employees.view"))):
        ...

نکته مهم: این Dependency پارامتر جدیدی به نام site_id تعریف نمی‌کند (چون این کار
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
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="احراز هویت نامعتبر یا منقضی‌شده است",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if token is None:
        raise unauthorized

    payload = decode_token(token)
    if payload is None or payload.get("type") != "access":
        raise unauthorized

    user_id = payload.get("sub")
    if user_id is None:
        raise unauthorized

    user = await UserRepository(db).get_by_id(int(user_id))
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
    """

    async def checker(
        request: Request,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        if current_user.is_superuser:
            return current_user

        if site_scoped:
            raw_site_id = request.path_params.get("site_id") or request.query_params.get("site_id")
            site_id = int(raw_site_id) if raw_site_id is not None else None
            codes = await UserRepository(db).get_permission_codes(current_user.id, site_id=site_id)
        else:
            # ⚠️ رفع یک باگ حیاتی: قبلاً اینجا هم get_permission_codes با
            # site_id=None صدا زده می‌شد — که طبق مستندات خودِ آن تابع، فقط
            # نقش‌های *سراسری* را می‌بیند، نه هر نقش سایت‌محوری. از وقتی
            # site_id برای انتصاب نقش اجباری شد، این یعنی همه Endpoint های
            # site_scoped=False (اکثریت قریب‌به‌اتفاق — مثل roles.manage،
            # sync.manage، vehicles.manage، system.backup) همیشه ۴۰۳
            # می‌دادند، حتی برای کاربری که واقعاً همان مجوز را (فقط سایت‌محور)
            # داشت. site_scoped=False یعنی «این Endpoint اصلاً به سایت خاصی
            # کاری ندارد»، پس باید هر انتصاب نقشی (سراسری یا هر سایتی) را
            # بپذیرد — نه فقط سراسری.
            codes = await UserRepository(db).get_all_permission_codes(current_user.id)

        if permission_code not in codes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"دسترسی لازم برای این عملیات را ندارید: {permission_code}",
            )
        return current_user

    return checker


async def require_superuser(current_user: User = Depends(get_current_user)) -> User:
    """
    ⚠️ برخلاف require_permission، این Dependency هیچ Permission Code ای
    قبول نمی‌کند — فقط و فقط Admin واقعی (is_superuser=True). برای
    تنظیماتی که عمداً نباید حتی از طریق RBAC به نقش‌های دیگر قابل‌اعطا
    باشند (مثلاً فهرست کلمات نامناسب گزارش انتقادات — چون خودِ همان
    دارنده مجوز مشاهده گزارش نباید بتواند این فهرست را ویرایش کند).
    """
    if not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="این عملیات فقط برای مدیر سیستم مجاز است")
    return current_user
