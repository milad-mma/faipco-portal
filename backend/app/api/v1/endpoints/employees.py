"""
Endpoint های پرسنل (/employees): لیست/جستجوی صفحه‌بندی‌شده، افزودن دستی پرسنل،
شمارش‌ها برای داشبورد، متولدین امروز و ری‌اکشن تبریک، عکس پرسنل، پاک‌سازی پرسنل
غیرفعال بدون سابقه، انتصاب مستقیم نقش، فعال/غیرفعال‌کردن دستی و تعیین/بازنشانی رمز عبور.

انتصاب نقش: به‌جای اینکه Admin مجبور باشد یک «کاربر» انتزاعی بسازد و به آن
نقش «مدیر سایت» بدهد، اینجا مستقیماً از بین پرسنل واقعی (که از Sync آمده‌اند)
جستجو می‌کند و نقش را به همان شخص می‌دهد. اگر آن پرسنل هنوز حساب کاربری
(User) نداشته باشد (چون هنوز خودش وارد نشده)، همین‌جا به‌صورت خودکار ساخته
می‌شود — دقیقاً با همان منطقی که هنگام ورود پرسنل (employee-login) استفاده می‌شود.
"""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.core.deps import get_current_user, require_permission
from app.core.site_access import get_accessible_site_ids, get_sites_with_permission
from app.services.employee_cleanup_service import (
    delete_orphaned_inactive_employees,
    find_orphaned_inactive_employees,
)
from app.core.persian_date import get_current_jalali_date
from app.core.security import WeakPasswordError
from app.db.session import get_db
from app.models.employee import Department, Employee
from app.models.site import Site
from app.models.site_transfer import SiteTransfer
from app.models.user import Role, User, UserRole
from app.repositories.user_repository import UserRepository
from app.models.birthday_reaction import BirthdayReaction, BirthdayReactionEmoji
from app.services.image_watermark import add_viewer_watermark, viewer_label_for
from app.services.birthday_reaction_service import BirthdayReactionError, BirthdayReactionService
from app.schemas.employee import (
    BirthdayEmployeeOut,
    SetBirthdayReactionIn,
    BirthdayVisibilityUpdate,
    EmployeeCreateIn,
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
    has_role: str | None = Query(
        default=None,
        description="فقط پرسنلی که این نقش (مثلاً attendance-pilot) را دارند — برای محدودکردن "
        "جست‌وجوهایی که فقط باید بین پرسنل واجدشرایط یک قابلیت خاص باشند",
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
    # هر کاربر لاگین‌شده می‌تواند برای انتخاب گیرنده اطلاعیه جستجو کند؛ اجازه واقعی
    # ارسال به هر شخص هنگام ثبت اطلاعیه در notice_service.py بررسی می‌شود.
    # با پیش‌فرض‌های include_inactive=False و include_portal_disabled=False فقط پرسنل
    # فعال در منبع و در پرتال برگردانده می‌شوند؛ صفحه «پرسنل» پنل Admin این دو را جدا کنترل می‌کند.
    _current_user: User = Depends(get_current_user),
):
    """
    فهرست صفحه‌بندی‌شده پرسنل با فیلتر (سایت، واحد، جستجو، نقش، وضعیت) و مرتب‌سازی.
    دسترسی: هر کاربر لاگین‌شده، ولی نتایج به سایت‌های در دسترس کاربر محدود می‌شود.
    خروجی: EmployeePageOut (آیتم‌های همین صفحه + تعداد کل).
    """
    # ایزوله‌سازی چندسایتی: کاربر فقط پرسنل سایت‌هایی را می‌بیند که در آن‌ها نقش دارد،
    # حتی اگر site_id دیگری در URL بفرستد. None یعنی بدون محدودیت (Admin یا نقش سراسری).
    accessible_site_ids = await get_accessible_site_ids(db, _current_user)

    def apply_filters(stmt):
        """همه فیلترهای درخواست را روی یک select اعمال می‌کند (مشترک بین کوئری شمارش و کوئری داده)."""
        if not include_inactive:
            stmt = stmt.where(Employee.is_active.is_(True))
        if not include_portal_disabled:
            stmt = stmt.where(Employee.is_enabled.is_(True))
        if site_id is not None:
            stmt = stmt.where(Employee.site_id == site_id)
        if accessible_site_ids is not None:
            stmt = stmt.where(Employee.site_id.in_(accessible_site_ids))
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
        # فقط پرسنلی که User متصلشان نقش has_role را دارد
        if has_role:
            role_exists = (
                select(UserRole.id)
                .join(Role, Role.id == UserRole.role_id)
                .join(User, User.id == UserRole.user_id)
                .where(User.employee_id == Employee.id, Role.name == has_role)
            )
            stmt = stmt.where(role_exists.exists())
        return stmt

    # تعداد کل نتایج (بدون صفحه‌بندی)
    count_stmt = apply_filters(
        select(func.count(Employee.id)).select_from(Employee)
    )
    total = (await db.execute(count_stmt)).scalar_one()

    sort_columns = _SORT_COLUMNS.get(sort_by, _SORT_COLUMNS["personnel_code"])  # sort_by ناشناخته → کد پرسنلی
    order_exprs = [col.desc() if sort_dir == "desc" else col.asc() for col in sort_columns]

    # داده‌های همین صفحه همراه نام سایت و واحد؛ Employee.id برای ترتیب پایدار اضافه می‌شود
    data_stmt = apply_filters(
        select(Employee, Site.name, Department.name)
        .join(Site, Site.id == Employee.site_id)
        .outerjoin(Department, Department.id == Employee.department_id)
    ).order_by(*order_exprs, Employee.id).limit(page_size).offset((page - 1) * page_size)

    result = await db.execute(data_stmt)
    rows = result.all()

    # has_custom_password روی User است نه Employee؛ با یک کوئری جدا فقط برای پرسنل همین صفحه خوانده می‌شود
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
            is_manually_created=e.is_manually_created,
        )
        for e, site_name, department_name in rows
    ]
    return EmployeePageOut(items=items, total=total)


@router.post("", response_model=EmployeeOut, status_code=status.HTTP_201_CREATED)
async def create_employee_manually(
    payload: EmployeeCreateIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("employees.create")),
):
    """
    مجوز: employees.create (برای سایت مقصد). خطاها: 403 سایت خارج از دسترسی، 404 سایت نامعتبر،
    400 واحد نامعتبر یا کد پرسنلی تکراری. خروجی: پرسنل ساخته‌شده.

    افزودن دستی یک پرسنل — فقط برای مواردی که واقعاً در هیچ منبع Sync
    موجود نیست (مثلاً هنوز به دیتابیس مبدأ اضافه نشده). این رکورد را
    Sync Engine نمی‌سازد، پس با یک نشانگر (is_manually_created) از رکوردهای
    عادی متمایز می‌شود — اگر بعداً همان personnel_code در منبع Sync واقعی
    هم ظاهر شود، طبق منطق موجود Sync Engine (Upsert بر اساس
    personnel_code+site_id) به‌طور طبیعی به‌روزرسانی/ادغام می‌شود.

    ایزوله‌سازی چندسایتی: Admin واقعی می‌تواند برای هر سایتی پرسنل
    اضافه کند؛ کاربر غیر-Admin با این مجوز فقط برای سایت‌هایی که خودش هم
    برایشان همین مجوز را دارد.
    """
    # بررسی دسترسی کاربر غیر-Admin به سایت مقصد
    if not current_user.is_superuser:
        accessible_site_ids = await get_sites_with_permission(db, current_user, "employees.create")
        if accessible_site_ids is not None and payload.site_id not in accessible_site_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="اجازه افزودن پرسنل برای این سایت را ندارید",
            )

    site = await db.get(Site, payload.site_id)
    if site is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="سایت یافت نشد")

    # واحد انتخاب‌شده باید متعلق به همان سایت باشد
    if payload.department_id is not None:
        department = await db.get(Department, payload.department_id)
        if department is None or department.site_id != payload.site_id:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="واحد سازمانی نامعتبر است")

    # جلوگیری از کد پرسنلی تکراری در همان سایت
    existing = await db.execute(
        select(Employee).where(Employee.site_id == payload.site_id, Employee.personnel_code == payload.personnel_code)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="پرسنلی با همین کد پرسنلی در این سایت از قبل وجود دارد",
        )

    employee = Employee(
        personnel_code=payload.personnel_code,
        national_code=payload.national_code,
        first_name=payload.first_name,
        last_name=payload.last_name,
        mobile=payload.mobile,
        site_id=payload.site_id,
        department_id=payload.department_id,
        position_title=payload.position_title,
        is_active=True,
        is_enabled=True,
        is_manually_created=True,
    )
    db.add(employee)
    await db.commit()
    await db.refresh(employee)

    return EmployeeOut(
        id=employee.id,
        personnel_code=employee.personnel_code,
        national_code=employee.national_code,
        first_name=employee.first_name,
        last_name=employee.last_name,
        mobile=employee.mobile,
        site_id=employee.site_id,
        department_id=employee.department_id,
        position_title=employee.position_title,
        is_active=employee.is_active,
        is_enabled=employee.is_enabled,
        has_custom_password=False,
        site_name=site.name,
        department_name=None,
        is_manually_created=True,
    )


@router.get("/portal-disabled-count")
async def count_portal_disabled_employees(
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """
    تعداد پرسنلِ فعال (از منبع Sync) که دسترسی پرتالشان دستی غیرفعال شده —
    برای کارت آمار داشبورد Admin (نشان می‌دهد چند نفر با وجود فعال بودن، به
    پرتال دسترسی ندارند). دسترسی: هر کاربر لاگین‌شده؛ ایزوله‌سازی چندسایتی مثل GET /employees.
    خروجی: {"count": عدد}.
    """
    accessible_site_ids = await get_accessible_site_ids(db, _current_user)
    stmt = select(func.count()).select_from(Employee).where(
        Employee.is_active.is_(True), Employee.is_enabled.is_(False)
    )
    if accessible_site_ids is not None:
        stmt = stmt.where(Employee.site_id.in_(accessible_site_ids))
    result = await db.execute(stmt)
    return {"count": result.scalar_one()}


@router.get("/birthdays-today", response_model=list[BirthdayEmployeeOut])
async def list_birthdays_today(
    respect_privacy: bool = False,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    پرسنل فعالی که امروز (تقویم شمسی) روز تولدشان است — برای کارت «متولدین
    روز جاری» در داشبورد Admin. تاریخ امروز بر اساس منطقه زمانی ایران محاسبه
    می‌شود (نه ساعت خام سرور که معمولاً UTC است) تا با birth_month/birth_day
    مقایسه شود (که خودشان از قبل شمسی ذخیره شده‌اند — نگاه کنید به سرویس Sync).

    respect_privacy (پیش‌فرض False): اگر True باشد، پرسنلی که خودشان
    hide_birthday_in_dashboard را فعال کرده‌اند از نتیجه کنار گذاشته
    می‌شوند. پیش‌فرض False است تا پنل Admin و ابزار ارسال پیام تبریک تولد
    (BirthdayMessagesPage) بدون تغییر همه پرسنل را ببینند — فقط داشبورد
    شخصی پرسنل (PersonalDashboardPage) این پارامتر را true می‌فرستد.

    دسترسی: هر کاربر لاگین‌شده؛ چون نام/واحد/سایت پرسنل برگردانده می‌شود، ایزوله‌سازی
    چندسایتی مثل GET /employees اعمال می‌شود. خروجی: لیست BirthdayEmployeeOut همراه ری‌اکشن‌ها.
    """
    accessible_site_ids = await get_accessible_site_ids(db, current_user)

    today_year, today_month, today_day = get_current_jalali_date()

    # پرسنل فعالی که روز و ماه تولدشان با امروز (شمسی) یکی است
    stmt = (
        select(Employee, Site.name, Department.name)
        .join(Site, Site.id == Employee.site_id)
        .outerjoin(Department, Department.id == Employee.department_id)
        .where(
            Employee.is_active.is_(True),
            Employee.birth_month == today_month,
            Employee.birth_day == today_day,
        )
    )
    if accessible_site_ids is not None:
        stmt = stmt.where(Employee.site_id.in_(accessible_site_ids))
    if respect_privacy:
        stmt = stmt.where(Employee.hide_birthday_in_dashboard.is_(False))
    result = await db.execute(stmt)
    rows = result.all()

    # ری‌اکشن‌های تبریک تولد با دو Query برای همه متولدین خوانده می‌شوند (نه یک Query به‌ازای هر نفر)؛
    # فهرست تبریک‌گویندگان برای همه قابل‌مشاهده است
    employee_ids = [e.id for e, _, _ in rows]
    reaction_service = BirthdayReactionService(db)
    reactions = await reaction_service.get_reactions_for_employees(employee_ids)
    my_reactions = await reaction_service.get_my_reactions(current_user, employee_ids)

    return [
        BirthdayEmployeeOut(
            id=e.id,
            first_name=e.first_name,
            last_name=e.last_name,
            site_name=site_name,
            department_name=department_name,
            reaction_counts=reactions.get(e.id, {}).get("counts", {}),
            reactors=reactions.get(e.id, {}).get("reactors", []),
            my_reaction=my_reactions.get(e.id),
            is_self=current_user.employee_id == e.id,
            has_photo=e.photo_thumbnail is not None,
        )
        for e, site_name, department_name in rows
    ]


@router.post("/birthdays/{employee_id}/reaction")
async def set_birthday_reaction(
    employee_id: int,
    payload: SetBirthdayReactionIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    ثبت/تغییر/برداشتن ری‌اکشن تبریک تولد برای پرسنل employee_id. کلیک روی همان ایموجی فعلی،
    آن را برمی‌دارد (Toggle). خودِ متولد نمی‌تواند به تولد خودش ری‌اکشن
    بزند و ری‌اکشن فقط در همان روز تولد مجاز است.
    دسترسی: هر کاربر لاگین‌شده. خطا: 400 برای ایموجی نامعتبر یا نقض این قواعد.
    """
    try:
        emoji = BirthdayReactionEmoji(payload.emoji)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="ایموجی نامعتبر است")
    try:
        return await BirthdayReactionService(db).set_reaction(current_user, employee_id, emoji)
    except BirthdayReactionError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.patch("/me/birthday-visibility", response_model=EmployeeOut)
async def update_my_birthday_visibility(
    payload: BirthdayVisibilityUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    تنظیم شخصی/خودانتخاب — هر پرسنل فقط برای خودش می‌تواند این را تغییر دهد
    (نه برای پرسنل دیگر، نه از پنل Admin — این عمداً یک قابلیت Self-service
    است). اگر کاربر جاری به هیچ رکورد Employee ای وصل نباشد (مثلاً یک
    حساب مدیریتی محض مثل admin)، ۴۰۴ برمی‌گردد. خروجی: رکورد پرسنل به‌روزشده.
    """
    if current_user.employee_id is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="حساب شما به هیچ رکورد پرسنلی وصل نیست",
        )
    employee = await db.get(Employee, current_user.employee_id)
    if employee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="پرسنل یافت نشد")
    employee.hide_birthday_in_dashboard = payload.hide_birthday_in_dashboard
    await db.commit()
    await db.refresh(employee)
    return employee


@router.get("/birthday-photo/{employee_id}")
async def get_birthday_related_photo_thumbnail(
    employee_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    عکس بندانگشتی (واترمارک‌شده با شناسه بیننده) برای کارت «متولدین امروز» و فهرست
    تبریک‌گویندگان؛ برای هر کاربر لاگین‌شده، ولی **فقط در همین دو زمینه**، نه به‌صورت عمومی.
    خطاها: 404 اگر عکس نباشد، 403 اگر پرسنل نه متولد امروز است نه تبریک‌گوی امسال.

    Endpoint اصلی (/photo-thumbnail) عمداً فقط به خودِ شخص یا Admin
    اجازه می‌دهد، چون تصویر چهره اطلاعات حساسی است. آن محدودیت
    دست‌نخورده می‌ماند؛ این مسیر جداگانه فقط عکس کسانی را می‌دهد که
    **امروز تولدشان است** یا **امروز به یک متولد تبریک گفته‌اند**.

    یعنی دسترسی هم محدود به زمینه است، هم خودکار روز بعد منقضی می‌شود -
    بدون اینکه عکس همه پرسنل برای همه باز شود.
    """
    jalali_year, month, day = get_current_jalali_date()

    employee = await db.get(Employee, employee_id)
    if employee is None or not employee.photo_thumbnail:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="عکسی برای این پرسنل ثبت نشده است")
    accessible_site_ids = await get_accessible_site_ids(db, current_user)  # None = همه‌ی سایت‌ها

    # متولد امروز فقط اگر در سایت‌های در دسترس بیننده باشد
    is_birthday_person = (
        employee.birth_month == month
        and employee.birth_day == day
        and (accessible_site_ids is None or employee.site_id in accessible_site_ids)
    )

    # در غیر این صورت: آیا این پرسنل امسال به متولدی در سایت‌های در دسترس بیننده تبریک گفته است؟
    # (تبریک‌گو ممکن است از سایت دیگری باشد، مثلاً مدیر سراسری)
    is_reactor = False
    if not is_birthday_person:
        reactor_query = (
            select(BirthdayReaction.id)
            .join(User, User.id == BirthdayReaction.reactor_user_id)
            .where(
                User.employee_id == employee_id,
                BirthdayReaction.jalali_year == jalali_year,
            )
        )
        if accessible_site_ids is not None:
            birthday_person = aliased(Employee)
            reactor_query = reactor_query.join(
                birthday_person, birthday_person.id == BirthdayReaction.birthday_employee_id
            ).where(birthday_person.site_id.in_(accessible_site_ids))
        reactor_check = await db.execute(reactor_query.limit(1))
        is_reactor = reactor_check.first() is not None

    if not (is_birthday_person or is_reactor):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="اجازه دسترسی به این عکس را ندارید")

    # شناسه بیننده به‌صورت واترمارک روی تصویر حک می‌شود تا هر عکس نشت‌یافته
    # قابل ردیابی به بیننده‌اش باشد (جلوگیری کامل از ذخیره تصویر در مرورگر ممکن نیست)
    viewer_employee = (
        await db.get(Employee, current_user.employee_id) if current_user.employee_id else None
    )
    content, media_type = add_viewer_watermark(
        employee.photo_thumbnail, viewer_label_for(current_user, viewer_employee)
    )
    return Response(
        content=content,
        media_type=media_type,
        # no-store: تصویر واترمارک‌شده مخصوص همین بیننده است و نباید در
        # Cache مرورگر/واسط بماند تا به بیننده دیگری سرو شود.
        headers={"Cache-Control": "no-store, private"},
    )


@router.get("/{employee_id}/photo-thumbnail")
async def get_employee_photo_thumbnail(
    employee_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    تصویر بندانگشتی پرسنل (از EmployeeExtendedInfo، طبق Mapping هر سایت).
    فقط خودِ همان شخص یا یک Admin کامل اجازه دیدن این عکس را دارد — نه هر
    کاربر لاگین‌شده‌ای برای هر پرسنلی، چون تصویر چهره اطلاعات حساسی است.
    خطاها: 403 برای دیگران، 404 اگر عکسی ثبت نشده باشد. خروجی: بایت‌های GIF.
    """
    if current_user.employee_id != employee_id and not current_user.is_superuser:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="اجازه دسترسی به این عکس را ندارید")

    employee = await db.get(Employee, employee_id)
    if employee is None or not employee.photo_thumbnail:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="عکسی برای این پرسنل ثبت نشده است")

    # ThumbnailImg در EmployeeExtendedInfo همیشه GIF است (بر اساس نمونه واقعی داده)
    return Response(content=employee.photo_thumbnail, media_type="image/gif")


async def _require_employee_site_permission(
    db: AsyncSession, user: User, employee: Employee, permission_code: str, allow_pending_transfer: bool = False
) -> None:
    """
    بررسی می‌کند سایت این پرسنل جزو سایت‌هایی باشد که کاربر permission_code را برایشان دارد؛ وگرنه 403.
    require_permission فقط «داشتن مجوز در جایی» را می‌سنجد؛ این تابع ایزوله‌سازی بین سایت‌ها را تضمین می‌کند.
    allow_pending_transfer: مدیر سایت قبلیِ پرسنلی که تازه منتقل شده و جابه‌جایی‌اش هنوز بازبینی نشده هم مجاز است
    (تا بتواند نقش‌های سایت خودش را برای او ببیند و حذف کند).
    """
    sites = await get_sites_with_permission(db, user, permission_code)  # None = سراسری یا superuser
    if sites is not None and employee.site_id not in sites and allow_pending_transfer:
        pending = await db.execute(
            select(SiteTransfer.id).where(
                SiteTransfer.employee_id == employee.id,
                SiteTransfer.reviewed_at.is_(None),
                SiteTransfer.from_site_id.in_(sites),
            ).limit(1)
        )
        if pending.first() is not None:
            return
    if sites is not None and employee.site_id not in sites:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="این پرسنل خارج از سایت‌های تحت اختیار شماست",
        )


# ---------- پاک‌سازی پرسنل غیرفعال «بدون سابقه» ----------


@router.get("/cleanup-orphaned-inactive/preview")
async def preview_orphaned_inactive_cleanup(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("users.manage")),
):
    """
    گزارش بدون‌اثر از پرسنلی که با اجرای Execute حذف می‌شوند (تعداد + فهرست با نام سایت).
    مجوز: users.manage (فقط پرسنل سایت‌هایی که این مجوز برایشان هست). معیار «بدون سابقه» در
    app/services/employee_cleanup_service.py است.
    """
    allowed_sites = await get_sites_with_permission(db, current_user, "users.manage")
    employees = await find_orphaned_inactive_employees(db, allowed_sites)
    # نام سایت‌ها با یک کوئری جمعی
    site_ids = {e.site_id for e in employees}
    sites_result = await db.execute(select(Site.id, Site.name).where(Site.id.in_(site_ids)))
    site_names = dict(sites_result.all())
    return {
        "count": len(employees),
        "items": [
            {
                "id": e.id,
                "personnel_code": e.personnel_code,
                "first_name": e.first_name,
                "last_name": e.last_name,
                "site_name": site_names.get(e.site_id, "—"),
            }
            for e in employees
        ],
    }


@router.post("/cleanup-orphaned-inactive/execute")
async def execute_orphaned_inactive_cleanup(
    confirm: bool = Query(default=False, description="باید صریحاً true باشد وگرنه هیچ حذفی انجام نمی‌شود"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("users.manage")),
):
    """
    حذف واقعی پرسنل غیرفعال بدون سابقه — فقط بعد از دیدن Preview و تأیید صریح Admin (confirm=true).
    مجوز: users.manage. خطا: 400 بدون confirm=true. خروجی: {"deleted_count": تعداد}.
    """
    if not confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="برای حذف واقعی باید confirm=true ارسال شود",
        )
    allowed_sites = await get_sites_with_permission(db, current_user, "users.manage")
    deleted_count = await delete_orphaned_inactive_employees(db, allowed_sites)
    return {"deleted_count": deleted_count}


@router.get("/count")
async def count_employees(
    site_id: int | None = Query(default=None, description="فیلتر بر اساس Site"),
    db: AsyncSession = Depends(get_db),
    _current_user: User = Depends(get_current_user),
):
    """
    شمارش پرسنل فعال (در منبع و در پرتال) با COUNT مستقیم از دیتابیس، برای کارت آمار داشبورد.
    ورودی اختیاری: site_id. دسترسی: هر کاربر لاگین‌شده، با همان ایزوله‌سازی چندسایتی GET /employees.
    خروجی: {"count": عدد}.
    """
    accessible_site_ids = await get_accessible_site_ids(db, _current_user)
    stmt = select(func.count()).select_from(Employee).where(
        Employee.is_active.is_(True), Employee.is_enabled.is_(True)
    )
    if site_id is not None:
        stmt = stmt.where(Employee.site_id == site_id)
    if accessible_site_ids is not None:
        stmt = stmt.where(Employee.site_id.in_(accessible_site_ids))
    result = await db.execute(stmt)
    return {"count": result.scalar_one()}


# ---------- انتصاب نقش مستقیم به یک پرسنل ----------

@router.get("/{employee_id}/roles", response_model=list[UserRoleOut])
async def list_employee_roles(
    employee_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("users.manage")),
):
    """
    نقش‌های فعلی حساب کاربری متصل به یک پرسنل را برمی‌گرداند (بدون حساب: لیست خالی).
    مجوز: users.manage برای سایت آن پرسنل. خطاها: 404 پرسنل، 403 خارج از سایت‌های مجاز.
    """
    employee = await db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="پرسنل یافت نشد")
    await _require_employee_site_permission(db, current_user, employee, "users.manage", allow_pending_transfer=True)

    result = await db.execute(select(User).where(User.employee_id == employee_id))
    user = result.scalar_one_or_none()
    if user is None:
        return []  # این پرسنل هنوز هیچ‌وقت وارد نشده، پس هیچ نقشی هم ندارد
    return await UserManagementService(db).list_user_roles(user.id)


@router.post("/{employee_id}/roles", response_model=list[UserRoleOut])
async def assign_role_to_employee(
    employee_id: int,
    payload: AssignRoleIn,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("users.manage")),
):
    """
    یک نقش (با محدوده سایت‌های اختیاری) را مستقیماً به پرسنل می‌دهد؛ در صورت نیاز حساب کاربری‌اش را می‌سازد.
    مجوز: users.manage برای سایت آن پرسنل و همه سایت‌های نقش. خطاها: 404 پرسنل، 403 خارج از محدوده، 400 نقش نامعتبر.
    خروجی: فهرست نقش‌های کاربر پس از انتصاب.
    """
    employee = await db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="پرسنل یافت نشد")

    # ایزوله‌سازی چندسایتی: require_permission فقط بررسی می‌کند کاربر «جایی» این مجوز را دارد؛
    # اینجا بررسی می‌شود که سایت همین پرسنل هم جزو سایت‌های تحت مجوز users.manage کاربر باشد.
    if not current_user.is_superuser:
        accessible_site_ids = await get_sites_with_permission(db, current_user, "users.manage")
        if accessible_site_ids is not None:
            if employee.site_id not in accessible_site_ids:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="اجازه مدیریت دسترسی این پرسنل را ندارید (خارج از سایت‌های تحت اختیار شما)",
                )
            # site_ids نقش هم نباید به سایت‌هایی خارج از اختیار کاربر گسترش یابد
            if any(sid not in accessible_site_ids for sid in payload.site_ids):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="اجازه اختصاص نقش برای این سایت(ها) را ندارید",
                )

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
    current_user: User = Depends(require_permission("users.manage")),
):
    """
    شناسه واحدهایی که این پرسنل هم‌اکنون سرپرست آن‌هاست (یک نفر می‌تواند چند واحد را سرپرستی کند).
    مجوز: users.manage برای سایت آن پرسنل. خطاها: 404 پرسنل، 403 خارج از سایت‌های مجاز.
    """
    employee = await db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="پرسنل یافت نشد")
    await _require_employee_site_permission(db, current_user, employee, "users.manage", allow_pending_transfer=True)

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
    current_user: User = Depends(require_permission("employees.update")),
):
    """
    فعال/غیرفعال‌کردن دستی یک پرسنل توسط Admin — کاملاً مستقل از is_active
    (که فقط Sync Engine کنترل می‌کند). این مقدار در ستون جداگانه‌ای
    (is_enabled) ذخیره می‌شود که هیچ اجرای Sync آن را بازنویسی نمی‌کند.
    مجوز: employees.update برای سایت آن پرسنل. خطاها: 404 پرسنل، 403 خارج از سایت‌های مجاز. خروجی: پرسنل به‌روزشده.
    """
    employee = await db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="پرسنل یافت نشد")
    await _require_employee_site_permission(db, current_user, employee, "employees.update")
    employee = await UserRepository(db).set_employee_enabled(employee, payload.is_enabled)

    result = await db.execute(select(User.has_custom_password).where(User.employee_id == employee.id))
    has_custom_password = result.scalar_one_or_none() or False  # بدون حساب کاربری → False
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
    current_user: User = Depends(require_permission("users.manage")),
):
    """
    تعیین دستی رمز عبور ورود یک پرسنل توسط Admin. بعد از این، ورود با کد ملی
    برای این پرسنل دیگر کار نمی‌کند — فقط با «کد پرسنلی + این رمز جدید».
    مجوز: users.manage برای سایت آن پرسنل. خطاها: 404 پرسنل، 403 خارج از سایت‌های مجاز، 400 رمز ضعیف.
    """
    employee = await db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="پرسنل یافت نشد")
    await _require_employee_site_permission(db, current_user, employee, "users.manage")
    try:
        await UserRepository(db).set_employee_password(employee, payload.new_password)
    except WeakPasswordError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.delete("/{employee_id}/password", status_code=status.HTTP_204_NO_CONTENT)
async def reset_employee_password(
    employee_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_permission("users.manage")),
):
    """
    بازگرداندن پرسنل به روش ورود پیش‌فرض (کد پرسنلی + کد ملی) — رمز عبور اختصاصی قبلی از کار می‌افتد.
    مجوز: users.manage برای سایت آن پرسنل. خطاها: 404 پرسنل، 403 خارج از سایت‌های مجاز.
    """
    employee = await db.get(Employee, employee_id)
    if employee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="پرسنل یافت نشد")
    await _require_employee_site_permission(db, current_user, employee, "users.manage")
    await UserRepository(db).reset_employee_to_default_login(employee)
