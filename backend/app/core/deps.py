"""
Dependency های مرکزی FastAPI:
- get_current_user: استخراج کاربر از Access Token
- require_permission: Factory برای بررسی RBAC، با پشتیبانی از نقش‌های Site-scoped

استفاده در هر Endpoint:
    @router.get("/employees")
    async def list_employees(user: User = Depends(require_permission("employees.view"))):
        ...
"""
from fastapi import Depends, HTTPException, Query, status
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


def require_permission(permission_code: str):
    """
    Dependency factory برای بررسی یک Permission مشخص.

    site_id به‌صورت Query Param اختیاری خوانده می‌شود تا نقش‌های Site-scoped
    (مثل "HR فقط سایت ۲") هم بررسی شوند. برای Endpoint هایی که به یک Site خاص
    مربوط‌اند (مثلاً /employees?site_id=2)، همین پارامتر به‌طور طبیعی استفاده می‌شود.
    """

    async def checker(
        site_id: int | None = Query(default=None),
        current_user: User = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> User:
        if current_user.is_superuser:
            return current_user

        codes = await UserRepository(db).get_permission_codes(current_user.id, site_id=site_id)
        if permission_code not in codes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"دسترسی لازم برای این عملیات را ندارید: {permission_code}",
            )
        return current_user

    return checker
