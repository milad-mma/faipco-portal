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
from app.models.user import Role
from app.schemas.user_management import (
    AccessOverviewEntry,
    AssignRoleIn,
    BulkAssignRoleIn,
    BulkAssignRoleOut,
    PermissionOut,
    RoleDetailOut,
    RoleOut,
    RoleUpsertIn,
    UserRoleOut,
)
from app.services.user_management_service import UserManagementService

router = APIRouter()


def _role_to_detail_out(role: Role) -> RoleDetailOut:
    """
    تبدیل شیء Role (که رابطه permissions رویش در واقع لیستی از RolePermission
    است، نه Permission مستقیم) به RoleDetailOut — چون این دو مدل داده فرق
    دارند، این تبدیل نمی‌تواند خودکار/مستقیم توسط FastAPI انجام شود.
    """
    return RoleDetailOut(
        id=role.id,
        name=role.name,
        description=role.description,
        is_system=role.is_system,
        permissions=[PermissionOut.model_validate(rp.permission) for rp in role.permissions],
    )


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


@router.post("/{user_id}/roles", response_model=list[UserRoleOut])
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


@router.post("/bulk-assign-role", response_model=BulkAssignRoleOut)
async def bulk_assign_role(
    payload: BulkAssignRoleIn,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("users.manage")),
):
    """
    یک نقش را هم‌زمان به فهرستی از پرسنل (employee_ids) یا همه پرسنل یک
    سایت/واحد (site_id/department_id) اختصاص می‌دهد — برای مواردی مثل
    فعال‌کردن یک قابلیت آزمایشی برای صدها نفر یک‌جا، بدون نیاز به انتصاب
    دستی یکی‌یکی.
    """
    try:
        result = await UserManagementService(db).bulk_assign_role(
            role_id=payload.role_id,
            employee_ids=payload.employee_ids,
            site_id=payload.site_id,
            department_id=payload.department_id,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return BulkAssignRoleOut(**result)


@router.delete("/roles/{user_role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def remove_role_assignment(
    user_role_id: int,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("users.manage")),
):
    removed = await UserManagementService(db).remove_role_assignment(user_role_id)
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="این انتصاب یافت نشد")


# ---------- پنل مدیریت نقش/مجوز — ساخت/ویرایش/حذف خودِ تعریف نقش‌ها ----------
# ⚠️ عمداً مسیر «/role-catalog» است، نه «/roles/{id}» — چون آن مسیر از قبل
# برای حذف یک *انتصاب* نقش (ردیف جدول user_roles) استفاده می‌شود؛ استفاده
# از همان الگو برای حذف خودِ *تعریف* نقش (ردیف جدول roles) با همان متد
# HTTP (DELETE) باعث تداخل مسیر می‌شد.


@router.get("/permissions", response_model=list[PermissionOut])
async def list_permissions(
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("users.manage")),
):
    return await UserManagementService(db).list_permissions()


@router.get("/role-catalog/{role_id}", response_model=RoleDetailOut)
async def get_role_detail(
    role_id: int,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("users.manage")),
):
    role = await UserManagementService(db).get_role_detail(role_id)
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="نقش یافت نشد")
    return _role_to_detail_out(role)


@router.post("/role-catalog", response_model=RoleDetailOut, status_code=status.HTTP_201_CREATED)
async def create_role(
    payload: RoleUpsertIn,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("users.manage")),
):
    try:
        role = await UserManagementService(db).create_role(payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    return _role_to_detail_out(role)


@router.patch("/role-catalog/{role_id}", response_model=RoleDetailOut)
async def update_role(
    role_id: int,
    payload: RoleUpsertIn,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("users.manage")),
):
    try:
        role = await UserManagementService(db).update_role(role_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="نقش یافت نشد")
    return _role_to_detail_out(role)


@router.delete("/role-catalog/{role_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_role(
    role_id: int,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("users.manage")),
):
    try:
        found = await UserManagementService(db).delete_role(role_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    if not found:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="نقش یافت نشد")
