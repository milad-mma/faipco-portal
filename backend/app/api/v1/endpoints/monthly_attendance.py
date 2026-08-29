"""
/monthly-attendance/report  (GET)  گزارش تردد ماهانه شخصی — از دستگاه‌های
                                     حضور و غیاب واقعی، در همان SQL Server
                                     سایت خودِ کاربر. فقط برای Siteهایی که
                                     یک AttendanceMapping (نگاشت جدول/ستون)
                                     تنظیم شده در دسترس است.

⚠️ کاملاً مستقل از سیستم آزمایشی GPS (در endpoints/attendance.py) — این یک
منبع داده کاملاً متفاوت (دستگاه حضور و غیاب واقعی کارخانه، نه خوداظهاری
GPS) است.

⚠️ امنیتی حیاتی: کد پرسنلی همیشه از خودِ Employee کاربر لاگین‌شده
(سشن/توکن) خوانده می‌شود — هرگز از پارامتر ورودی درخواست. هیچ پارامتری
نمی‌تواند این را Override کند.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.persian_date import get_current_jalali_year_month
from app.db.session import get_db
from app.models.employee import Employee
from app.models.site import AttendanceMapping, SiteConnection
from app.models.user import User
from app.services.monthly_attendance_service import MonthlyAttendanceError, get_monthly_attendance

router = APIRouter()


@router.get("/report")
async def monthly_attendance_report(
    year: int | None = Query(default=None),
    month: int | None = Query(default=None, ge=1, le=12),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.employee_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="این کاربر به هیچ پرسنلی متصل نیست")

    employee = await db.get(Employee, current_user.employee_id)
    if employee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="پرسنل یافت نشد")

    # ⚠️ وجود یا نبود AttendanceMapping برای سایت این پرسنل، خودِ «آیا این
    # گزارش برایش فعال است؟» را مشخص می‌کند — نه یک فلگ boolean جدا.
    mapping_result = await db.execute(select(AttendanceMapping).where(AttendanceMapping.site_id == employee.site_id))
    mapping = mapping_result.scalar_one_or_none()
    if mapping is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="گزارش تردد ماهانه برای سایت شما فعال نیست",
        )

    conn_result = await db.execute(select(SiteConnection).where(SiteConnection.site_id == employee.site_id))
    site_connection = conn_result.scalar_one_or_none()
    if site_connection is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="اتصال دیتابیس این سایت هنوز تنظیم نشده است",
        )

    if year is None or month is None:
        current_year, current_month = get_current_jalali_year_month()
        year = year or current_year
        month = month or current_month

    try:
        return await get_monthly_attendance(
            site_connection, mapping, personnel_code=employee.personnel_code, year=year, month=month
        )
    except MonthlyAttendanceError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
