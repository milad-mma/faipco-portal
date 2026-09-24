"""
کمک‌تابع‌های مشترک برای محدودسازی دسترسی بر اساس Site — استفاده در هر
Endpoint ای که داده‌اش (پرسنل، گزارش حضور، و...) باید بین سایت‌ها ایزوله باشد:
- get_accessible_site_ids: سایت‌هایی که کاربر به‌طور کلی مجاز به دیدن آن‌هاست
- get_sites_with_permission: سایت‌هایی که کاربر یک Permission مشخص را برایشان دارد
- get_sites_with_permission_prefix: همان، برای گروهی از Permissionها با پیشوند مشترک

پیش‌فرض طراحی: این پروژه Multi-Site است — هر سایت پرسنل، مدیر، و
واحدهای سازمانی جدای خودش را دارد (معمولاً حتی به یک دیتابیس منبع کاملاً
جدا هم وصل است). یک نقش Site-scoped (مثلاً site_manager یا hr-manager
وقتی برای یک Site خاص انتصاب شده) نباید هیچ داده‌ای از سایت دیگر ببیند —
مگر Admin واقعی (is_superuser).
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.employee import Department, Employee
from app.models.site import Site
from app.models.user import Permission, Role, RolePermission, User, UserRole

# مجوزهایی که فقط به کار خودِ شخص مربوط‌اند و دسترسی به داده‌ی دیگران نمی‌دهند؛
# نقشی که فقط این‌ها را دارد (مثل attendance-pilot) در تعیین سایت‌های قابل‌مشاهده حساب نمی‌شود.
SELF_ONLY_PERMISSIONS = frozenset({"attendance.clock_in_out"})


async def all_site_ids(db: AsyncSession) -> set[int]:
    """شناسه‌ی همه‌ی سایت‌های تعریف‌شده (فعال و غیرفعال)."""
    result = await db.execute(select(Site.id))
    return {row[0] for row in result.all()}


def covers_all_sites(site_ids: set[int], every_site: set[int]) -> bool:
    """
    آیا این مجموعه همه‌ی سایت‌های موجود را پوشش می‌دهد؟ داشتن یک نقش/مجوز برای همه‌ی سایت‌ها
    معادل «سراسری» است (بدون سایت تعریف‌شده → False).
    """
    return bool(every_site) and every_site <= site_ids


def _data_role_ids():
    """زیرکوئری شناسه‌ی نقش‌هایی که حداقل یک مجوز غیر از SELF_ONLY_PERMISSIONS دارند."""
    return (
        select(RolePermission.role_id)
        .join(Permission, Permission.id == RolePermission.permission_id)
        .where(Permission.code.not_in(SELF_ONLY_PERMISSIONS))
    )


async def get_accessible_site_ids(db: AsyncSession, user: User) -> set[int] | None:
    """
    «این کاربر اصولاً مجاز به دیدن داده کدام سایت‌هاست؟» — یک قانون کلی و
    محافظه‌کارانه (نه مخصوص یک Permission خاص)، برای Endpoint هایی که به
    چند دلیل مختلف (هدف‌گیری اطلاعیه، مدیریت حضور، سرپرستی واحد) باید بین
    پرسنل جست‌وجو کنند — بدون این‌که هرکدام Permission Code جداگانه‌ای
    داشته باشند.

    خروجی None یعنی «بدون محدودیت» (Admin واقعی، نقش سراسری، یا نقش/سرپرستی در همه‌ی
    سایت‌های موجود). خروجی یک Set (حتی خالی) یعنی دقیقاً همان سایت‌ها مجازند.
    نقش‌هایی که فقط مجوزهای شخصی (SELF_ONLY_PERMISSIONS) دارند در این محاسبه حساب نمی‌شوند.

    منطق:
    1. Admin واقعی → None (نامحدود).
    2. حداقل یک نقش سراسری (UserRole.site_id IS NULL) دارد → None — چون
       نقش‌های سراسری (middle_manager، acc_manager، hr-manager وقتی
       سراسری انتصاب شده) ذاتاً برای کار بین‌سایتی طراحی شده‌اند.
    3. وگرنه: اتحاد (Union) سایت‌هایی که یا (الف) یک نقش Site-scoped برایشان
       دارد، یا (ب) سرپرست حداقل یک واحد در آن سایت است.
    4. اگر هیچ‌کدام از بالا صدق نکند (پرسنل عادی بدون هیچ نقشی) → فقط سایت
       خودش (از روی Employee.site_id، اگر حساب کاربری‌اش به یک پرسنل وصل
       باشد).
    """
    if user.is_superuser:
        return None

    # آیا حداقل یک نقش سراسری (site_id خالی) با مجوز داده دارد؟
    org_wide_result = await db.execute(
        select(UserRole.id)
        .where(
            UserRole.user_id == user.id,
            UserRole.site_id.is_(None),
            UserRole.role_id.in_(_data_role_ids()),
        )
        .limit(1)
    )
    if org_wide_result.scalar_one_or_none() is not None:
        return None

    site_ids: set[int] = set()

    # سایت‌های نقش‌های Site-scoped
    scoped_result = await db.execute(
        select(UserRole.site_id).where(
            UserRole.user_id == user.id,
            UserRole.site_id.is_not(None),
            UserRole.role_id.in_(_data_role_ids()),
        )
    )
    site_ids.update(row[0] for row in scoped_result.all())

    # سایت‌های واحدهایی که کاربر سرپرستشان است
    supervised_result = await db.execute(
        select(Department.site_id).where(Department.supervisor_user_id == user.id)
    )
    site_ids.update(row[0] for row in supervised_result.all())

    # نقش/سرپرستی در همه‌ی سایت‌ها = بدون محدودیت
    if site_ids and covers_all_sites(site_ids, await all_site_ids(db)):
        return None

    # پرسنل عادی بدون نقش: فقط سایت خودش
    if not site_ids and user.employee_id is not None:
        employee = await db.get(Employee, user.employee_id)
        if employee is not None:
            site_ids.add(employee.site_id)

    return site_ids


async def get_sites_with_permission(db: AsyncSession, user: User, permission_code: str) -> set[int] | None:
    """
    مثل get_accessible_site_ids، ولی دقیق‌تر — فقط سایت‌هایی که کاربر
    مشخصاً همین یک Permission Code را برایشان دارد (نه هر نوع نقشی).
    برای Endpoint هایی که یک Permission مشخص و منفرد دارند (مثل
    attendance.view_clock_records) و باید نتیجه را به همان سایت‌ها محدود
    کنند، نه فقط تصمیم دودویی «اجازه دارد یا نه» بگیرند.

    خروجی None یعنی «بدون محدودیت» (Admin واقعی، یا این Permission را سراسری
    یا برای همه‌ی سایت‌های موجود دارد). خروجی Set خالی یعنی این Permission را
    برای هیچ سایتی ندارد (باید ۴۰۳ بدهد).
    """
    if user.is_superuser:
        return None

    # site_id همه انتصاب‌های نقشی که این Permission را دارند (None = انتصاب سراسری)
    stmt = (
        select(UserRole.site_id)
        .join(Role, Role.id == UserRole.role_id)
        .join(RolePermission, RolePermission.role_id == Role.id)
        .join(Permission, Permission.id == RolePermission.permission_id)
        .where(UserRole.user_id == user.id, Permission.code == permission_code)
    )
    result = await db.execute(stmt)
    site_ids_raw = [row[0] for row in result.all()]

    if any(site_id is None for site_id in site_ids_raw):
        return None  # حداقل یک انتصاب سراسری این Permission را دارد

    sites = set(site_ids_raw)
    # این مجوز برای همه‌ی سایت‌های موجود = سراسری
    if sites and covers_all_sites(sites, await all_site_ids(db)):
        return None
    return sites


async def get_sites_with_permission_prefix(db: AsyncSession, user: User, code_prefix: str) -> dict:
    """
    مثل get_sites_with_permission، ولی برای گروهی از Permission ها که همه
    با یک پیشوند مشترک شروع می‌شوند (مثلاً leave_requests.view.type. که
    هرکدام مخصوص یک LeaveRequestType است - کد مجوز از قبل مشخص نیست، چون
    نوع‌ها به‌صورت پویا ساخته می‌شوند).

    خروجی: دیکشنری {کد کامل Permission: مجموعه site_id یا None (نامحدود)}
    - فقط شامل کدهایی که این کاربر واقعاً حداقل یک بار دارد (چه سراسری،
    چه محدود به یک سایت). Admin واقعی → دیکشنری خالی برمی‌گرداند؛ فراخوان
    باید جداگانه user.is_superuser را برای «دسترسی نامحدود» چک کند.
    """
    if user.is_superuser:
        return {}

    # همه جفت‌های (کد Permission، site_id) کاربر برای کدهای با این پیشوند
    stmt = (
        select(Permission.code, UserRole.site_id)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .join(Role, Role.id == RolePermission.role_id)
        .join(UserRole, UserRole.role_id == Role.id)
        .where(UserRole.user_id == user.id, Permission.code.like(f"{code_prefix}%"))
    )
    result = await db.execute(stmt)

    # تجمیع: انتصاب سراسری (None) بر مجموعه سایت‌ها غلبه می‌کند
    mapping: dict = {}
    for code, site_id in result.all():
        if code in mapping and mapping[code] is None:
            continue  # این کد با انتصاب سراسری نامحدود شده است
        if site_id is None:
            mapping[code] = None
        else:
            mapping.setdefault(code, set()).add(site_id)
    # کدی که برای همه‌ی سایت‌های موجود داده شده معادل سراسری است
    scoped = [code for code, sites in mapping.items() if sites is not None]
    if scoped:
        every_site = await all_site_ids(db)
        for code in scoped:
            if covers_all_sites(mapping[code], every_site):
                mapping[code] = None
    return mapping
