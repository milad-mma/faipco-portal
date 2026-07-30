"""
Dependency های مرکزی FastAPI:
- get_current_user: استخراج کاربر از Access Token
- require_permission: Factory برای بررسی RBAC، با پشتیبانی از نقش‌های Site-scoped

استفاده در هر Endpoint:
    @router.get("/employees")
    async def list_employees(user: User = Depends(require_permission("employees.view"))):
        ...

    # وقتی خودِ Route هم site_id دارد (چه Path و چه Query)، site_scoped=True بدهید:
    @router.get("/{site_id}/logs")
    async def list_logs(site_id: int, user: User = Depends(require_permission("sync.view", site_scoped=True))):
        ...
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

    نکته مهم طراحی: این تابع دیگر پارامتر جدیدی به نام site_id به FastAPI
    اضافه نمی‌کند (قبلاً این کار با Query(default=None) انجام می‌شد که با
    Route هایی مثل /sites/{site_id}/connection تداخل نام پیدا می‌کرد — چون
    site_id در آن‌ها Path Parameter است، نه Query — و FastAPI موقع ساخت
    Dependency Graph روی این تناقض خطا می‌داد و کل برنامه Start نمی‌شد).

    به‌جایش، اگر site_scoped=True باشد، مقدار site_id مستقیماً از خودِ
    Request خوانده می‌شود (اول از Path Params، بعد از Query Params) —
    یعنی هیچ پارامتر رقیبی تعریف نمی‌شود و Route می‌تواند site_id را به هر
    شکلی (Path یا Query) که خودش نیاز دارد اعلام کند.
    """

    async def checker(
        request: Request,
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        if current_user.is_superuser:
            return current_user

        site_id: int | None = None
        if site_scoped:
            raw_site_id = request.path_params.get("site_id") or request.query_params.get("site_id")
            if raw_site_id is not None:
                site_id = int(raw_site_id)

        codes = await UserRepository(db).get_permission_codes(current_user.id, site_id=site_id)
        if permission_code not in codes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"دسترسی لازم برای این عملیات را ندارید: {permission_code}",
            )
        return current_user

    return checker
