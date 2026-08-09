"""
Endpoint های پرسنل: لیست/جستجو، انتصاب مستقیم نقش به یک پرسنل مشخص، فعال/غیرفعال‌کردن
دستی، و تعیین دستی رمز عبور ورود.

نکته طراحی مهم: به‌جای اینکه Admin مجبور باشد یک «کاربر» انتزاعی بسازد و به آن
نقش «مدیر سایت» بدهد، اینجا مستقیماً از بین پرسنل واقعی (که از Sync آمده‌اند)
جستجو می‌کند و نقش را به همان شخص می‌دهد. اگر آن پرسنل هنوز حساب کاربری
(User) نداشته باشد (چون هنوز خودش وارد نشده)، همین‌جا به‌صورت خودکار ساخته
می‌شود — دقیقاً با همان منطقی که هنگام ورود پرسنل (employee-login) استفاده می‌شود.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_permission
from app.db.session import get_db
from app.models.employee import Department, Employee
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.employee import EmployeeActiveUpdate, EmployeeOut, EmployeePasswordSet
from app.schemas.user_management import AssignRoleIn, UserRoleOut
from app.services.user_management_service import UserManagementService

router = APIRouter()


@router.get("", response_model=list[EmployeeOut])
async def list_employees(
    site_id: int | None = Query(default=None, description="فیلتر بر اساس Site"),
    search: str | None = Query(
        default=None, description="جستجو در نام، نام خانوادگی، کد پرسنلی یا کد ملی"
    ),
    include_inactive: bool = Query(
        default=False,
        description="پرسنل غیرفعال را هم نشان بده — فقط برای صفحه مدیریت پرسنل (Admin) استفاده می‌شود",
    ),
    db: AsyncSession = Depends(get_db),
    # هر کاربر لاگین‌شده (نه فقط Admin) باید بتواند برای انتخاب گیرنده اطلاعیه
    # در بین پرسنل جستجو کند. اعتبارسنجی واقعی این‌که «آیا اجازه ارسال به این
    # شخص را دارد یا نه» موقع ثبت اطلاعیه در notice_service.py انجام می‌شود.
    # پیش‌فرض include_inactive=False همان رفتار قبلی را برای این جستجو حفظ
    # می‌کند (پرسنل غیرفعال هدف اطلاعیه قرار نمی‌گیرند)؛ فقط صفحه «پرسنل» در
    # پنل Admin با include_inactive=True درخواست می‌دهد تا بتواند دوباره فعال کند.
    _current_user: User = Depends(get_current_user),
):
    stmt = select(Employee).limit(200)
    if not include_inactive:
        stmt = stmt.where(Employee.is_active.is_(True))
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


@router.get("/count")
async def count_employees(
    site_id: int | None = Query(default=None, description="فیلتر بر اساس Site"),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """
    شمارش دقیق پرسنل فعال — برخلاف GET /employees که برای کارایی سقف ۲۰۰ رکورد
    دارد، این Endpoint تعداد واقعی را مستقیماً با COUNT از دیتابیس می‌خواند
    (برای کارت آمار در داشبورد استفاده می‌شود).
    """
    stmt = select(func.count()).select_from(Employee).where(Employee.is_active.is_(True))
    if site_id is not None:
        stmt = stmt.where(Employee.site_id == site_id)
    result = await db.execute(stmt)
    return {"count": result.scalar_one()}


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
    try:
        return await UserManagementService(db).assign_role(user.id, payload)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/{employee_id}/supervised-departments", response_model=list[int])
async def list_supervised_departments(
    employee_id: int,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("users.manage")),
):
    """شناسه واحدهایی که این پرسنل هم‌اکنون سرپرست آن‌هاست (یک نفر می‌تواند چند واحد را سرپرستی کند)."""
    employee = await db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="پرسنل یافت نشد")

    result = await db.execute(select(User).where(User.employee_id == employee_id))
    user = result.scalar_one_or_none()
    if user is None:
        return []  # هنوز حساب کاربری ندارد، پس سرپرست هیچ واحدی هم نیست

    result = await db.execute(select(Department.id).where(Department.supervisor_user_id == user.id))
    return [row[0] for row in result.all()]


# ---------- فعال/غیرفعال‌کردن دستی + تعیین رمز عبور (پنل Admin) ----------

@router.patch("/{employee_id}", response_model=EmployeeOut)
async def update_employee_active_state(
    employee_id: int,
    payload: EmployeeActiveUpdate,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("employees.update")),
):
    """
    فعال/غیرفعال‌کردن دستی یک پرسنل توسط Admin — مستقل از Sync Engine.
    نکته مهم: اگر Mapping این Site ستون is_active منبع را می‌خواند، اجرای بعدی
    Sync (خودکار یا دستی) دوباره این مقدار را بر اساس منبع بازنویسی می‌کند —
    یعنی این تغییر دستی فقط تا اجرای بعدی Sync برای همین پرسنل پایدار است.
    """
    employee = await db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="پرسنل یافت نشد")
    employee.is_active = payload.is_active
    await db.commit()
    await db.refresh(employee)
    return employee


@router.put("/{employee_id}/password", status_code=status.HTTP_204_NO_CONTENT)
async def set_employee_password(
    employee_id: int,
    payload: EmployeePasswordSet,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("users.manage")),
):
    """
    تعیین دستی رمز عبور ورود یک پرسنل توسط Admin. این رمز یک روش ورود
    جایگزین اضافه می‌کند (کد پرسنلی + این رمز)؛ ورود با کد پرسنلی + کد ملی
    همچنان مثل قبل کار می‌کند.
    """
    employee = await db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="پرسنل یافت نشد")
    await UserRepository(db).set_employee_password(employee, payload.new_password)
