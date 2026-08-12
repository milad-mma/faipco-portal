"""
Endpoint های پرسنل: لیست/جستجو، انتصاب مستقیم نقش به یک پرسنل مشخص، فعال/غیرفعال‌کردن
دستی، و تعیین دستی رمز عبور ورود.

نکته طراحی مهم: به‌جای اینکه Admin مجبور باشد یک «کاربر» انتزاعی بسازد و به آن
نقش «مدیر سایت» بدهد، اینجا مستقیماً از بین پرسنل واقعی (که از Sync آمده‌اند)
جستجو می‌کند و نقش را به همان شخص می‌دهد. اگر آن پرسنل هنوز حساب کاربری
(User) نداشته باشد (چون هنوز خودش وارد نشده)، همین‌جا به‌صورت خودکار ساخته
می‌شود — دقیقاً با همان منطقی که هنگام ورود پرسنل (employee-login) استفاده می‌شود.
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user, require_permission
from app.db.session import get_db
from app.models.employee import Department, Employee
from app.models.site import Site
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.schemas.employee import (
    BirthdayEmployeeOut,
    EmployeeEnabledUpdate,
    EmployeeOut,
    EmployeePageOut,
    EmployeePasswordSet,
)
from app.schemas.user_management import AssignRoleIn, UserRoleOut
from app.services.user_management_service import UserManagementService

router = APIRouter()

# فیلدهای قابل Sort در GET /employees — کلید همان چیزی است که فرانت‌اند در
# sort_by می‌فرستد؛ مقدار، ستون(های) SQLAlchemy واقعی برای ORDER BY است (برای
# نام کامل، هم first_name و هم last_name به‌ترتیب استفاده می‌شوند).
_SORT_COLUMNS: dict[str, list] = {
    "personnel_code": [Employee.personnel_code],
    "full_name": [Employee.first_name, Employee.last_name],
    "national_code": [Employee.national_code],
    "mobile": [Employee.mobile],
    "site_name": [Site.name],
    "department_name": [Department.name],
    "is_enabled": [Employee.is_enabled],
    "is_active": [Employee.is_active],
}


@router.get("", response_model=EmployeePageOut)
async def list_employees(
    site_id: int | None = Query(default=None, description="فیلتر بر اساس Site"),
    department_id: list[int] | None = Query(
        default=None,
        description="فیلتر بر اساس یک یا چند واحد سازمانی — برای محدودسازی جستجوی سرپرست واحد "
        "به فقط پرسنل همان واحد(های) خودش استفاده می‌شود (نه کل سازمان)",
    ),
    search: str | None = Query(
        default=None, description="جستجو در نام، نام خانوادگی، کد پرسنلی یا کد ملی"
    ),
    include_inactive: bool = Query(
        default=False,
        description="پرسنلی که در منبع Sync دیگر فعال نیستند (is_active=False) را هم نشان بده — "
        "فقط صفحه مدیریت پرسنل با یک فیلتر جدا این را روشن می‌کند",
    ),
    include_portal_disabled: bool = Query(
        default=False,
        description="پرسنلی که دسترسی پرتالشان دستی غیرفعال شده (is_enabled=False) را هم نشان بده",
    ),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=25, ge=1, le=200),
    sort_by: str = Query(default="personnel_code"),
    sort_dir: str = Query(default="asc", pattern="^(asc|desc)$"),
    db: AsyncSession = Depends(get_db),
    # هر کاربر لاگین‌شده (نه فقط Admin) باید بتواند برای انتخاب گیرنده اطلاعیه
    # در بین پرسنل جستجو کند. اعتبارسنجی واقعی این‌که «آیا اجازه ارسال به این
    # شخص را دارد یا نه» موقع ثبت اطلاعیه در notice_service.py انجام می‌شود.
    # پیش‌فرض include_inactive=False و include_portal_disabled=False همان
    # رفتار قبلی را برای این جستجو حفظ می‌کند (فقط پرسنل فعال و در پرتال
    # فعال، هدف اطلاعیه قرار می‌گیرند)؛ فقط صفحه «پرسنل» در پنل Admin این دو
    # پرچم را جدا از هم کنترل می‌کند تا هم بتواند پرسنل غیرفعال در پرتال را
    # مدیریت کند و هم در صورت نیاز پرسنل غیرفعال از منبع را ببیند.
    _current_user: User = Depends(get_current_user),
):
    def apply_filters(stmt):
        if not include_inactive:
            stmt = stmt.where(Employee.is_active.is_(True))
        if not include_portal_disabled:
            stmt = stmt.where(Employee.is_enabled.is_(True))
        if site_id is not None:
            stmt = stmt.where(Employee.site_id == site_id)
        if department_id:
            stmt = stmt.where(Employee.department_id.in_(department_id))
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
        return stmt

    count_stmt = apply_filters(
        select(func.count(Employee.id)).select_from(Employee)
    )
    total = (await db.execute(count_stmt)).scalar_one()

    sort_columns = _SORT_COLUMNS.get(sort_by, _SORT_COLUMNS["personnel_code"])
    order_exprs = [col.desc() if sort_dir == "desc" else col.asc() for col in sort_columns]

    data_stmt = apply_filters(
        select(Employee, Site.name, Department.name)
        .join(Site, Site.id == Employee.site_id)
        .outerjoin(Department, Department.id == Employee.department_id)
    ).order_by(*order_exprs, Employee.id).limit(page_size).offset((page - 1) * page_size)

    result = await db.execute(data_stmt)
    rows = result.all()

    # has_custom_password روی User است نه Employee — با یک کوئری جدا (فقط برای
    # همین صفحه از پرسنل) به هرکدام وصل می‌شود.
    custom_password_by_employee: dict[int, bool] = {}
    employee_ids = [row[0].id for row in rows]
    if employee_ids:
        user_result = await db.execute(
            select(User.employee_id, User.has_custom_password).where(User.employee_id.in_(employee_ids))
        )
        custom_password_by_employee = dict(user_result.all())

    items = [
        EmployeeOut(
            id=e.id,
            personnel_code=e.personnel_code,
            national_code=e.national_code,
            first_name=e.first_name,
            last_name=e.last_name,
            mobile=e.mobile,
            site_id=e.site_id,
            department_id=e.department_id,
            position_title=e.position_title,
            is_active=e.is_active,
            is_enabled=e.is_enabled,
            has_custom_password=custom_password_by_employee.get(e.id, False),
            site_name=site_name,
            department_name=department_name,
        )
        for e, site_name, department_name in rows
    ]
    return EmployeePageOut(items=items, total=total)


@router.get("/portal-disabled-count")
async def count_portal_disabled_employees(
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """
    تعداد پرسنلِ فعال (از منبع Sync) که دسترسی پرتالشان دستی غیرفعال شده —
    برای کارت آمار داشبورد Admin (نشان می‌دهد چند نفر با وجود فعال بودن، به
    پرتال دسترسی ندارند).
    """
    stmt = select(func.count()).select_from(Employee).where(
        Employee.is_active.is_(True), Employee.is_enabled.is_(False)
    )
    result = await db.execute(stmt)
    return {"count": result.scalar_one()}


@router.get("/birthdays-today", response_model=list[BirthdayEmployeeOut])
async def list_birthdays_today(
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """
    پرسنل فعالی که امروز (تقویم شمسی) روز تولدشان است — برای کارت «متولدین
    روز جاری» در داشبورد Admin. تاریخ امروز (میلادی، ساعت سرور) به شمسی
    تبدیل می‌شود تا با birth_month/birth_day مقایسه شود (که خودشان از قبل
    شمسی ذخیره شده‌اند — نگاه کنید به سرویس Sync).
    """
    import jdatetime

    today_jalali = jdatetime.date.fromgregorian(date=datetime.now().date())

    stmt = (
        select(Employee, Site.name, Department.name)
        .join(Site, Site.id == Employee.site_id)
        .outerjoin(Department, Department.id == Employee.department_id)
        .where(
            Employee.is_active.is_(True),
            Employee.birth_month == today_jalali.month,
            Employee.birth_day == today_jalali.day,
        )
    )
    result = await db.execute(stmt)
    return [
        BirthdayEmployeeOut(
            id=e.id,
            first_name=e.first_name,
            last_name=e.last_name,
            site_name=site_name,
            department_name=department_name,
        )
        for e, site_name, department_name in result.all()
    ]


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
    stmt = select(func.count()).select_from(Employee).where(
        Employee.is_active.is_(True), Employee.is_enabled.is_(True)
    )
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
async def update_employee_enabled_state(
    employee_id: int,
    payload: EmployeeEnabledUpdate,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("employees.update")),
):
    """
    فعال/غیرفعال‌کردن دستی یک پرسنل توسط Admin — کاملاً مستقل از is_active
    (که فقط Sync Engine کنترل می‌کند). این مقدار در ستون جداگانه‌ای
    (is_enabled) ذخیره می‌شود که هیچ اجرای Sync آن را بازنویسی نمی‌کند.
    """
    employee = await db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="پرسنل یافت نشد")
    employee = await UserRepository(db).set_employee_enabled(employee, payload.is_enabled)

    result = await db.execute(select(User.has_custom_password).where(User.employee_id == employee.id))
    has_custom_password = result.scalar_one_or_none() or False
    return EmployeeOut(
        id=employee.id,
        personnel_code=employee.personnel_code,
        national_code=employee.national_code,
        first_name=employee.first_name,
        last_name=employee.last_name,
        mobile=employee.mobile,
        site_id=employee.site_id,
        department_id=employee.department_id,
        is_active=employee.is_active,
        is_enabled=employee.is_enabled,
        has_custom_password=has_custom_password,
    )


@router.put("/{employee_id}/password", status_code=status.HTTP_204_NO_CONTENT)
async def set_employee_password(
    employee_id: int,
    payload: EmployeePasswordSet,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("users.manage")),
):
    """
    تعیین دستی رمز عبور ورود یک پرسنل توسط Admin. بعد از این، ورود با کد ملی
    برای این پرسنل دیگر کار نمی‌کند — فقط با «کد پرسنلی + این رمز جدید».
    """
    employee = await db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="پرسنل یافت نشد")
    await UserRepository(db).set_employee_password(employee, payload.new_password)


@router.delete("/{employee_id}/password", status_code=status.HTTP_204_NO_CONTENT)
async def reset_employee_password(
    employee_id: int,
    db: AsyncSession = Depends(get_db),
    _user=Depends(require_permission("users.manage")),
):
    """بازگرداندن پرسنل به روش ورود پیش‌فرض (کد پرسنلی + کد ملی) — رمز عبور اختصاصی قبلی از کار می‌افتد."""
    employee = await db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="پرسنل یافت نشد")
    await UserRepository(db).reset_employee_to_default_login(employee)
