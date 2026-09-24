"""
Endpointهای مدیریت کاربران، انتصاب نقش و تعریف نقش‌ها.
- نمای کلی دسترسی‌ها، فهرست نقش‌ها و مجوزها.
- انتصاب/حذف نقش برای یک کاربر و انتصاب گروهی نقش (با محدودیت سایت برای غیر superuser).
- ساخت/ویرایش/حذف تعریف نقش‌ها زیر مسیر /role-catalog.
نقش «مدیر سایت» (با site_id) یا نقش‌های سراسری «مدیرعامل»/«مدیر منابع انسانی» (بدون site_id)
تعیین می‌کند کاربر به چه کسانی اجازه‌ی ارسال اطلاعیه دارد (notice_service.py).
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_permission
from app.db.session import get_db
from app.core.site_access import get_sites_with_permission
from app.models.employee import Department, Employee
from app.repositories.user_repository import UserRepository
from app.models.user import Role, User, UserRole
from app.schemas.user_management import (
    AccessOverviewEntry,
    AssignRoleIn,
    BulkAssignRoleIn,
    BulkAssignRoleOut,
    PermissionOut,
    RoleDetailOut,
    RoleOut,
    RoleUpsertIn,
    SiteTransferOut,
    UserRoleOut,
)
from app.services.user_management_service import UserManagementService

router = APIRouter()


def _role_to_detail_out(role: Role) -> RoleDetailOut:
    """
    ورودی: شیء Role که role.permissions آن لیستی از RolePermission است.
    خروجی: RoleDetailOut با لیست Permissionها (تبدیل دستی، چون ساختار دو مدل متفاوت است).
    """
    return RoleDetailOut(
        id=role.id,
        name=role.name,
        description=role.description,
        is_system=role.is_system,
        permissions=[PermissionOut.model_validate(rp.permission) for rp in role.permissions],
    )


async def _require_org_wide_users_manage(db: AsyncSession, user: User) -> None:
    """
    تعریف نقش‌ها بین همه‌ی سایت‌ها مشترک است؛ ساخت/ویرایش/حذف آن فقط با users.manage سراسری
    (یا superuser) مجاز است. در غیر این صورت 403.
    """
    if await get_sites_with_permission(db, user, "users.manage") is not None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="تعریف نقش‌ها بین همه‌ی سایت‌ها مشترک است و فقط با مجوز users.manage برای همه‌ی سایت‌ها قابل تغییر است",
        )


@router.get("/site-transfers", response_model=list[SiteTransferOut])
async def list_site_transfers(
    pending_only: bool = True,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("users.manage")),
):
    """
    جابه‌جایی‌های پرسنل بین سایت‌ها (ثبت‌شده توسط Sync) با نقش‌ها و سرپرستی‌های فعلی هر نفر،
    برای بازبینی نقش‌های سایت قبلی. مجوز: users.manage؛ غیر superuser فقط جابه‌جایی‌هایی را می‌بیند
    که سایت مبدأ یا مقصدشان تحت اختیار اوست. pending_only=false همه‌ی موارد را برمی‌گرداند.
    """
    accessible_site_ids = None
    if not current_user.is_superuser:
        accessible_site_ids = await get_sites_with_permission(db, current_user, "users.manage")
    return await UserManagementService(db).list_site_transfers(accessible_site_ids, pending_only)


@router.post("/site-transfers/{transfer_id}/review", status_code=status.HTTP_204_NO_CONTENT)
async def review_site_transfer(
    transfer_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("users.manage")),
):
    """یک جابه‌جایی را «بازبینی‌شده» علامت می‌زند. مجوز: users.manage؛ مورد ناموجود یا خارج از سایت‌های مجاز → 404."""
    accessible_site_ids = None
    if not current_user.is_superuser:
        accessible_site_ids = await get_sites_with_permission(db, current_user, "users.manage")
    if not await UserManagementService(db).mark_site_transfer_reviewed(transfer_id, current_user.id, accessible_site_ids):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="جابه‌جایی یافت نشد")


@router.get("/access-overview", response_model=list[AccessOverviewEntry])
async def access_overview(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("users.manage")),
):
    """
    جدول همه‌ی کسانی که نقش سازمانی یا سرپرستی واحد دارند (برای پنل مدیریت دسترسی).
    دسترسی: مجوز users.manage؛ غیر superuser فقط سایت‌های تحت اختیار خود را می‌بیند.
    """
    accessible_site_ids = None  # None یعنی بدون محدودیت سایت
    if not current_user.is_superuser:
        accessible_site_ids = await get_sites_with_permission(db, current_user, "users.manage")
    return await UserManagementService(db).get_access_overview(accessible_site_ids)


@router.get("/roles", response_model=list[RoleOut])
async def list_roles(
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("roles.manage")),
):
    """فهرست همه‌ی نقش‌ها را برمی‌گرداند. دسترسی: مجوز roles.manage."""
    return await UserManagementService(db).list_roles()


@router.get("/{user_id}/roles", response_model=list[UserRoleOut])
async def list_user_roles(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("users.manage")),
):
    """
    فهرست انتصاب‌های نقش یک کاربر را برمی‌گرداند. دسترسی: مجوز users.manage برای سایت پرسنلِ آن کاربر
    (کاربر بدون پرسنل فقط با مجوز سراسری). خطا: 403 خارج از سایت‌های مجاز.
    """
    manage_sites = await get_sites_with_permission(db, current_user, "users.manage")
    if manage_sites is not None:
        target_site = (
            await db.execute(select(Employee.site_id).join(User, User.employee_id == Employee.id).where(User.id == user_id))
        ).scalar_one_or_none()
        if target_site not in manage_sites:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="این کاربر خارج از سایت‌های تحت اختیار شماست")
    return await UserManagementService(db).list_user_roles(user_id)


@router.post("/{user_id}/roles", response_model=list[UserRoleOut])
async def assign_role(
    user_id: int,
    payload: AssignRoleIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("users.manage")),
):
    """
    یک نقش (در صورت نیاز برای چند سایت) به کاربر اختصاص می‌دهد و انتصاب‌های فعلی او را برمی‌گرداند.
    دسترسی: users.manage؛ غیر superuser فقط برای کاربران و سایت‌های تحت اختیار خود.
    خطاها: 404 (کاربر یافت نشد)، 403 (خارج از سایت‌های مجاز)، 400 (داده‌ی نامعتبر).
    """
    # محدودیت چندسایتی (مشابه /employees/{id}/roles): کاربر هدف و سایت‌های درخواستی باید در اختیار فراخواننده باشند
    if not current_user.is_superuser:
        target_user = await UserRepository(db).get_by_id(user_id)
        if target_user is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="کاربر یافت نشد")
        accessible_site_ids = await get_sites_with_permission(db, current_user, "users.manage")
        if accessible_site_ids is not None:
            # سایت کاربر هدف از روی پرسنل متصل به او تعیین می‌شود (کاربر بدون پرسنل = بدون سایت)
            target_site_id = None
            if target_user.employee_id is not None:
                employee = await db.get(Employee, target_user.employee_id)
                target_site_id = employee.site_id if employee else None
            if target_site_id not in accessible_site_ids:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="اجازه مدیریت دسترسی این کاربر را ندارید (خارج از سایت‌های تحت اختیار شما)",
                )
            # همه‌ی سایت‌هایی که نقش برایشان داده می‌شود باید در اختیار فراخواننده باشند
            if any(sid not in accessible_site_ids for sid in payload.site_ids):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="اجازه اختصاص نقش برای این سایت(ها) را ندارید",
                )

    try:
        return await UserManagementService(db).assign_role(user_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/bulk-assign-role", response_model=BulkAssignRoleOut)
async def bulk_assign_role(
    payload: BulkAssignRoleIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("users.manage")),
):
    """
    یک نقش را یک‌جا به فهرستی از پرسنل (employee_ids) یا همه‌ی پرسنل یک سایت/واحد اختصاص می‌دهد و آمار نتیجه را برمی‌گرداند.
    دسترسی: users.manage؛ غیر superuser فقط برای سایت/واحد/پرسنل تحت اختیار خود.
    خطاها: 403 (خارج از سایت‌های مجاز)، 400 (داده‌ی نامعتبر).
    """
    # محدودیت چندسایتی: سایت، واحد و تک‌تک پرسنل هدف باید در سایت‌های تحت اختیار باشند
    if not current_user.is_superuser:
        accessible_site_ids = await get_sites_with_permission(db, current_user, "users.manage")
        if accessible_site_ids is not None:
            if payload.site_id is not None and payload.site_id not in accessible_site_ids:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN, detail="اجازه مدیریت دسترسی این سایت را ندارید"
                )
            if payload.department_id is not None:
                department = await db.get(Department, payload.department_id)
                if department is None or department.site_id not in accessible_site_ids:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN, detail="اجازه مدیریت دسترسی این واحد را ندارید"
                    )
            if payload.employee_ids:
                # شمارش پرسنلی از فهرست که سایتشان خارج از سایت‌های مجاز است
                result = await db.execute(
                    select(func.count()).select_from(Employee).where(
                        Employee.id.in_(payload.employee_ids), Employee.site_id.not_in(accessible_site_ids)
                    )
                )
                if result.scalar_one() > 0:
                    raise HTTPException(
                        status_code=status.HTTP_403_FORBIDDEN,
                        detail="بعضی از این پرسنل خارج از سایت‌های تحت اختیار شما هستند",
                    )

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
    current_user: User = Depends(require_permission("users.manage")),
):
    """
    یک انتصاب نقش (ردیف user_roles) را حذف می‌کند (پاسخ 204).
    دسترسی: users.manage برای سایت همان انتصاب؛ انتصاب سراسری فقط با users.manage سراسری.
    خطاها: 403 خارج از سایت‌های مجاز، 404 اگر انتصاب وجود نداشته باشد.
    """
    assignment = await db.get(UserRole, user_role_id)
    if assignment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="این انتصاب یافت نشد")
    manage_sites = await get_sites_with_permission(db, current_user, "users.manage")
    if manage_sites is not None and (assignment.site_id is None or assignment.site_id not in manage_sites):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="اجازه حذف این انتصاب را ندارید")
    removed = await UserManagementService(db).remove_role_assignment(user_role_id)
    if not removed:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="این انتصاب یافت نشد")


# ---------- پنل مدیریت نقش/مجوز: ساخت/ویرایش/حذف تعریف نقش‌ها ----------
# مسیر «/role-catalog» جدا از «/roles/{id}» است، چون DELETE /roles/{id} انتصاب نقش (جدول user_roles)
# را حذف می‌کند و DELETE /role-catalog/{id} خودِ تعریف نقش (جدول roles) را.


@router.get("/permissions", response_model=list[PermissionOut])
async def list_permissions(
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("users.manage")),
):
    """فهرست همه‌ی مجوزهای تعریف‌شده را برمی‌گرداند. دسترسی: مجوز users.manage."""
    return await UserManagementService(db).list_permissions()


@router.get("/role-catalog/{role_id}", response_model=RoleDetailOut)
async def get_role_detail(
    role_id: int,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("users.manage")),
):
    """
    جزئیات یک نقش همراه با مجوزهایش را برمی‌گرداند.
    دسترسی: مجوز users.manage. خطا: 404 اگر نقش وجود نداشته باشد.
    """
    role = await UserManagementService(db).get_role_detail(role_id)
    if role is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="نقش یافت نشد")
    return _role_to_detail_out(role)


@router.post("/role-catalog", response_model=RoleDetailOut, status_code=status.HTTP_201_CREATED)
async def create_role(
    payload: RoleUpsertIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("users.manage")),
):
    """
    نقش جدید با مجوزهای داده‌شده می‌سازد و جزئیات آن را برمی‌گرداند (201).
    دسترسی: مجوز users.manage سراسری (در غیر این صورت 403). خطا: 400 (نام رزرو superadmin یا نام تکراری).
    """
    await _require_org_wide_users_manage(db, current_user)
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
    current_user: User = Depends(require_permission("users.manage")),
):
    """
    نام، توضیح و مجوزهای یک نقش را ویرایش می‌کند و جزئیات جدید را برمی‌گرداند.
    دسترسی: مجوز users.manage سراسری (در غیر این صورت 403). خطاها: 400 (superadmin یا نام تکراری)، 404 (نقش یافت نشد).
    """
    await _require_org_wide_users_manage(db, current_user)
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
    current_user: User = Depends(require_permission("users.manage")),
):
    """
    تعریف یک نقش را حذف می‌کند (پاسخ 204).
    دسترسی: مجوز users.manage سراسری (در غیر این صورت 403). خطاها: 400 (superadmin یا نقشی که هنوز انتصاب دارد)، 404 (نقش یافت نشد).
    """
    await _require_org_wide_users_manage(db, current_user)
    try:
        found = await UserManagementService(db).delete_role(role_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    if not found:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="نقش یافت نشد")
