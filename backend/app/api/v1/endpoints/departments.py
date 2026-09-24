"""
Endpoint های مدیریت واحدهای سازمانی (Department).

شامل: فهرست واحدها، ایجاد واحد جدید و انتصاب سرپرست واحد.
سرپرست هر واحد به‌صورت خودکار اجازه ارسال اطلاعیه به همان واحد
(و پرسنل همان واحد) را پیدا می‌کند — بدون نیاز به تعریف Role جداگانه.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_permission
from app.core.site_access import get_accessible_site_ids
from app.core.site_permission_deps import require_site_permission
from app.db.session import get_db
from app.models.employee import Department, Employee
from app.models.user import User
from app.schemas.department import AssignSupervisorIn, DepartmentCreate, DepartmentOut
from app.services.department_service import DepartmentService

router = APIRouter()


@router.get("", response_model=list[DepartmentOut])
async def list_departments(
    site_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    فهرست واحدهای سازمانی را (اختیاری: فقط یک سایت) برمی‌گرداند.
    دسترسی: هر کاربر لاگین‌شده، فقط واحدهای سایت‌هایی که به آن‌ها دسترسی دارد.
    """
    allowed = await get_accessible_site_ids(db, current_user)
    return await DepartmentService(db).list_departments(site_id=site_id, allowed_site_ids=allowed)


@router.post("", response_model=DepartmentOut)
async def create_department(
    payload: DepartmentCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("sites.manage")),
):
    """یک واحد سازمانی جدید می‌سازد و آن را برمی‌گرداند. مجوز لازم: sites.manage برای همان سایت (وگرنه 403)."""
    await require_site_permission(db, current_user, payload.site_id, "sites.manage")
    return await DepartmentService(db).create_department(payload)


@router.put("/{department_id}/supervisor", response_model=DepartmentOut)
async def assign_supervisor(
    department_id: int,
    payload: AssignSupervisorIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("users.manage")),
):
    """
    پرسنل داده‌شده را سرپرست واحد می‌کند (یا با employee_id خالی، سرپرست را برمی‌دارد).
    مجوز لازم: users.manage برای سایت همان واحد، و اگر سرپرست از پرسنل سایت دیگری است، برای سایت او هم
    (سرپرستی به سرپرست دسترسی به سایت واحد می‌دهد). خطاها: 400 ورودی نامعتبر، 403 سایت غیرمجاز، 404 واحد یافت نشد.
    """
    target = await db.get(Department, department_id)
    if target is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="واحد سازمانی یافت نشد")
    await require_site_permission(db, current_user, target.site_id, "users.manage")
    if payload.employee_id is not None:
        person = await db.get(Employee, payload.employee_id)
        if person is not None and person.site_id != target.site_id:
            await require_site_permission(db, current_user, person.site_id, "users.manage")
    try:
        department = await DepartmentService(db).assign_supervisor(department_id, payload.employee_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    if department is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="واحد سازمانی یافت نشد")
    return department
