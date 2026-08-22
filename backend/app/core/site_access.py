"""
کمک‌تابع‌های مشترک برای محدودسازی دسترسی بر اساس Site — استفاده در هر
Endpoint ای که داده‌اش (پرسنل، گزارش حضور، و...) باید بین سایت‌ها ایزوله
باشد، نه فقط بین‌المللی/سراسری قابل‌مشاهده.

⚠️ پیش‌فرض طراحی: این پروژه Multi-Site است — هر سایت پرسنل، مدیر، و
واحدهای سازمانی جدای خودش را دارد (معمولاً حتی به یک دیتابیس منبع کاملاً
جدا هم وصل است). یک نقش Site-scoped (مثلاً site_manager یا hr-manager
وقتی برای یک Site خاص انتصاب شده) نباید هیچ داده‌ای از سایت دیگر ببیند —
مگر Admin واقعی (is_superuser).
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.employee import Department, Employee
from app.models.user import Permission, Role, RolePermission, User, UserRole


async def get_accessible_site_ids(db: AsyncSession, user: User) -> set[int] | None:
    """
    «این کاربر اصولاً مجاز به دیدن داده کدام سایت‌هاست؟» — یک قانون کلی و
    محافظه‌کارانه (نه مخصوص یک Permission خاص)، برای Endpoint هایی که به
    چند دلیل مختلف (هدف‌گیری اطلاعیه، مدیریت حضور، سرپرستی واحد) باید بین
    پرسنل جست‌وجو کنند — بدون این‌که هرکدام Permission Code جداگانه‌ای
    داشته باشند.

    خروجی None یعنی «بدون محدودیت» (Admin واقعی، یا حداقل یک نقش سراسری
    دارد). خروجی یک Set (حتی خالی) یعنی دقیقاً همان سایت‌ها مجازند.

    منطق:
    1. Admin واقعی → None (نامحدود).
    2. حداقل یک نقش سراسری (UserRole.site_id IS NULL) دارد → None — چون
       نقش‌های سراسری فعلی (middle_manager، acc_manager، hr-manager وقتی
       سراسری انتصاب شده) ذاتاً برای کار بین‌سایتی طراحی شده‌اند.
    3. وگرنه: اتحاد (Union) سایت‌هایی که یا (الف) یک نقش Site-scoped برایشان
       دارد، یا (ب) سرپرست حداقل یک واحد در آن سایت است.
    4. اگر هیچ‌کدام از بالا صدق نکند (پرسنل عادی بدون هیچ نقشی) → فقط سایت
       خودش (از روی Employee.site_id، اگر حساب کاربری‌اش به یک پرسنل وصل
       باشد).
    """
    if user.is_superuser:
        return None

    org_wide_result = await db.execute(
        select(UserRole.id).where(UserRole.user_id == user.id, UserRole.site_id.is_(None)).limit(1)
    )
    if org_wide_result.scalar_one_or_none() is not None:
        return None

    site_ids: set[int] = set()

    scoped_result = await db.execute(
        select(UserRole.site_id).where(UserRole.user_id == user.id, UserRole.site_id.is_not(None))
    )
    site_ids.update(row[0] for row in scoped_result.all())

    supervised_result = await db.execute(
        select(Department.site_id).where(Department.supervisor_user_id == user.id)
    )
    site_ids.update(row[0] for row in supervised_result.all())

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

    خروجی None یعنی «بدون محدودیت» (Admin واقعی، یا این Permission را
    سراسری دارد). خروجی Set خالی یعنی این Permission را برای هیچ سایتی
    ندارد (باید ۴۰۳ بدهد).
    """
    if user.is_superuser:
        return None

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

    return set(site_ids_raw)
