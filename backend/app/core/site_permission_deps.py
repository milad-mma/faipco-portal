"""
کمک‌تابع مشترک برای Endpoint هایی که site_id مستقیماً در Path/Query
ندارند (باید ابتدا از رکورد مرتبط Resolve شود) - برای جلوگیری از تکرار
همین منطق در چند فایل Endpoint مختلف (evaluation_structure.py،
evaluation_periods.py، evaluation_forms.py).

استفاده معمول:
    period = await db.get(EvaluationPeriod, period_id)
    await require_site_permission(db, current_user, period.site_id, "performance.periods.manage")

⚠️ site_id می‌تواند None باشد (یعنی «سراسری» / همه سایت‌ها) - در این
حالت فقط کاربرانی که همین Permission را به‌صورت سراسری دارند (نه فقط
برای یک سایت خاص) مجازند؛ اجازه نمی‌دهیم کسی که فقط برای یک سایت مجوز
دارد، یک رکورد «سراسری» (site_id=None) بسازد یا ویرایش کند.
"""
from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.site_access import get_sites_with_permission
from app.models.user import User


async def require_site_permission(
    db: AsyncSession, user: User, site_id: int | None, permission_code: str
) -> None:
    if user.is_superuser:
        return
    sites = await get_sites_with_permission(db, user, permission_code)
    if sites is None:
        return  # این Permission را به‌صورت سراسری دارد - بدون محدودیت
    if site_id is None:
        # رکورد سراسری (site_id=None) - فقط با مجوز سراسری قابل‌دسترسی است
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"فقط با مجوز سراسری {permission_code} می‌توانید موارد «همه سایت‌ها» را مدیریت کنید",
        )
    if site_id not in sites:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail=f"دسترسی لازم برای این عملیات را ندارید: {permission_code}"
        )
