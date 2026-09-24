"""
توابع کمکی «کد شعبه» هر سایت، وقتی چند سایت یک دیتابیس کاراوب مشترک دارند.

منبع واحد: «کد شعبه این سایت» در نگاشت پرسنل (EmployeeMapping.
branch_code_value). بقیه بخش‌ها (درخواست مرخصی/ماموریت، تقویم تعطیلات،
نوشتن در کارکرد) اگر مقدار جداگانه‌ای تنظیم نشده باشد از همین استفاده می‌کنند
تا لازم نباشد یک عدد در چند جا تکرار شود.

در کاراوب شناسه‌های Employee.Emp_No، Shifts.Shift_No، Sections.Sec_No و
Cards.Card_No سراسری (یکتا بین همه شعبه‌ها) هستند، پس خواندن بر اساس کد
پرسنلی نیازی به فیلتر شعبه ندارد. جدول‌هایی که فقط با شعبه معنا دارند:
WF_Requests (فهرست درخواست‌ها)، Calen (تقویم تعطیلات، یکتا روی شعبه+سال+ماه).
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.employee import EmployeeMapping


async def get_site_branch_value(db: AsyncSession, site_id: int) -> str | None:
    """
    ورودی: شناسه سایت. کد شعبه (branch_code_value) را از نگاشت پرسنل سایت برمی‌گرداند؛
    اگر نگاشت، ستون شعبه یا مقدار آن خالی باشد None برمی‌گرداند.
    """
    result = await db.execute(
        select(EmployeeMapping.branch_code_column, EmployeeMapping.branch_code_value).where(
            EmployeeMapping.site_id == site_id
        )
    )
    row = result.first()
    # فقط وقتی هم ستون و هم مقدار شعبه پر باشد، فیلتر شعبه معتبر است
    if not row or not (row[0] or "").strip() or not (row[1] or "").strip():
        return None
    return row[1].strip()


def as_int(value) -> int | None:
    """مقدار را (پس از strip) به int تبدیل می‌کند؛ اگر قابل تبدیل نباشد None برمی‌گرداند."""
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None
