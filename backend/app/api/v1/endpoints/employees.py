"""
Endpoint های پرسنل: لیست/جستجو، و انتصاب مستقیم نقش به یک پرسنل مشخص.

نکته طراحی مهم: به‌جای اینکه Admin مجبور باشد یک «کاربر» انتزاعی بسازد و به آن
نقش «مدیر سایت» بدهد، اینجا مستقیماً از بین پرسنل واقعی (که از Sync آمده‌اند)
جستجو می‌کند و نقش را به همان شخص می‌دهد. اگر آن پرسنل هنوز حساب کاربری
(User) نداشته باشد (چون هنوز خودش وارد نشده)، همین‌جا به‌صورت خودکار ساخته
می‌شود — دقیقاً با همان منطقی که هنگام ورود پرسنل (employee-login) استفاده می‌شود.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import require_permission
from app.db.session import get_db
from app.models.employee import Employee
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.employee import EmployeeOut
from app.schemas.user_management import AssignRoleIn, UserRoleOut
from app.services.user_management_service import UserManagementService

router = APIRouter()


@router.get("", response_model=list[EmployeeOut])
async def list_employees(
    site_id: int | None = Query(default=None, description="فیلتر بر اساس Site"),
    search: str | None = Query(
        default=None, description="جستجو در نام، نام خانوادگی، کد پرسنلی یا کد ملی"
    ),
    db: AsyncSession = Depends(get_db),
    _current_user=Depends(require_permission("employees.view", site_scoped=True)),
):
    stmt = select(Employee).where(Employee.is_active.is_(True)).limit(200)
    if site_id is not None:
        stmt = stmt.where(Employee.site_id == site_id)
    if search:
        pattern = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                Employee.first_name.ilike(pattern),
                Employee.last_name.ilike(pattern),
                Employee.personnel_code.ilike(pattern),
                Employee.national_code.ilike(pattern),
            )
        )
    result = await db.execute(stmt)
    return result.scalars().all()


# ---------- انتصاب نقش مستقیم به یک پرسنل ----------

@router.get("/{employee_id}/roles", response_model=list[UserRoleOut])
async def list_employee_roles(
    employee_id: int,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("users.manage")),
):
    employee = await db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="پرسنل یافت نشد")

    result = await db.execute(select(User).where(User.employee_id == employee_id))
    user = result.scalar_one_or_none()
    if user is None:
        return []  # این پرسنل هنوز هیچ‌وقت وارد نشده، پس هیچ نقشی هم ندارد
    return await UserManagementService(db).list_user_roles(user.id)


@router.post("/{employee_id}/roles", response_model=UserRoleOut)
async def assign_role_to_employee(
    employee_id: int,
    payload: AssignRoleIn,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("users.manage")),
):
    employee = await db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="پرسنل یافت نشد")

    # اگر این پرسنل هنوز حساب کاربری نداشته باشد، همین‌جا ساخته می‌شود
    # (دقیقاً همان User که بعداً با ورود کد پرسنلی/کد ملی خودش هم استفاده خواهد شد)
    user = await UserRepository(db).get_or_create_employee_user(employee)
    return await UserManagementService(db).assign_role(user.id, payload)
