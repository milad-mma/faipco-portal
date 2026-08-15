"""
Endpoint های مدیریت کاربران و انتصاب نقش.

انتصاب نقش «مدیر سایت» به یک کاربر (با site_id مشخص) یا نقش سراسری «مدیرعامل»/
«مدیر منابع انسانی» (بدون site_id) دقیقاً همان چیزی است که تعیین می‌کند آن کاربر
اجازه ارسال اطلاعیه به چه کسانی را دارد (به سرویس notice_service.py مراجعه کنید).
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_permission
from app.db.session import get_db
from app.schemas.user_management import (
    AccessOverviewEntry,
    AssignRoleIn,
    RoleOut,
    UserManagementOut,
    UserRoleOut,
)
from app.services.user_management_service import UserManagementService

router = APIRouter()


@router.get("", response_model=list[UserManagementOut])
async def list_users(
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("users.manage")),
):
    return await UserManagementService(db).list_users()


@router.get("/access-overview", response_model=list[AccessOverviewEntry])
async def access_overview(
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("users.manage")),
):
    """جدول کامل همه کسانی که نقش سازمانی یا سرپرستی واحد دارند — برای پنل مدیریت دسترسی."""
    return await UserManagementService(db).get_access_overview()


@router.get("/roles", response_model=list[RoleOut])
async def list_roles(
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("roles.manage")),
):
    return await UserManagementService(db).list_roles()


@router.get("/{user_id}/roles", response_model=list[UserRoleOut])
async def list_user_roles(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("users.manage")),
):
    return await UserManagementService(db).list_user_roles(user_id)


@router.post("/{user_id}/roles", response_model=UserRoleOut)
async def assign_role(
    user_id: int,
    payload: AssignRoleIn,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("users.manage")),
):
    try:
        return await UserManagementService(db).assign_role(user_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/roles/{user_role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_role_assignment(
    user_role_id: int,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("users.manage")),
):
    removed = await UserManagementService(db).remove_role_assignment(user_role_id)
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="این انتصاب یافت نشد")
