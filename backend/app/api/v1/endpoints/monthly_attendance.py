"""
Endpoint گزارش تردد ماهانه‌ی شخصی.

GET /monthly-attendance/report — گزارش تردد ماه شمسی کاربر لاگین‌شده را از
دستگاه‌های حضور و غیاب واقعی (SQL Server سایت خودِ پرسنل) می‌خواند. فقط
برای سایت‌هایی در دسترس است که AttendanceMapping (نگاشت جدول/ستون) دارند.

این ماژول مستقل از سیستم GPS در endpoints/attendance.py است؛ منبع داده‌اش
دستگاه حضور و غیاب کارخانه است، نه خوداظهاری GPS.

نکته‌ی امنیتی: کد پرسنلی همیشه از Employee کاربر لاگین‌شده (توکن) خوانده
می‌شود و هیچ پارامتر ورودی نمی‌تواند آن را تغییر دهد.
"""
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.core.persian_date import get_current_jalali_year_month
from app.db.session import get_db
from app.models.employee import Employee
from app.models.leave_request import LeaveRequestMapping, LeaveRequestType
from app.models.site import AttendanceMapping, SiteConnection
from app.models.user import User
from app.services import kara_attendance_overlay
from app.services.kara_schema import KaraNames
from app.services.monthly_attendance_service import MonthlyAttendanceError, get_monthly_attendance
from app.services.site_branch import get_site_branch_value
from app.services.access_gate_service import AccessGateBlocked, AccessGateService

router = APIRouter()


@router.get("/report")
async def monthly_attendance_report(
    year: int | None = Query(default=None),
    month: int | None = Query(default=None, ge=1, le=12),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    گزارش تردد ماهانه‌ی خودِ کاربر لاگین‌شده را برمی‌گرداند (هر کاربر متصل به پرسنل).
    ورودی: سال/ماه شمسی اختیاری (پیش‌فرض: ماه جاری). خروجی: ساختار get_monthly_attendance.
    خطاها: 403 اگر دروازه‌ی دسترسی بسته باشد، 404 اگر پرسنل/نگاشت/اتصال سایت نباشد، 502 در خطای SQL Server.
    """
    # دروازه‌ی دسترسی: اگر ادمین اجبار را فعال کرده و کاربر اطلاعیه‌ی خوانده‌نشده
    # یا ارزیابی انجام‌نشده دارد، 403 برمی‌گردد
    try:
        await AccessGateService(db).check(current_user, "attendance_report")
    except AccessGateBlocked as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

    # کاربر باید به یک پرسنل متصل باشد
    if current_user.employee_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="این کاربر به هیچ پرسنلی متصل نیست")

    employee = await db.get(Employee, current_user.employee_id)
    if employee is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="پرسنل یافت نشد")

    # وجود AttendanceMapping برای سایت پرسنل، به‌تنهایی یعنی گزارش برای او فعال است
    mapping_result = await db.execute(select(AttendanceMapping).where(AttendanceMapping.site_id == employee.site_id))
    mapping = mapping_result.scalar_one_or_none()
    if mapping is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="گزارش تردد ماهانه برای سایت شما فعال نیست",
        )

    # اتصال SQL Server سایت
    conn_result = await db.execute(select(SiteConnection).where(SiteConnection.site_id == employee.site_id))
    site_connection = conn_result.scalar_one_or_none()
    if site_connection is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="اتصال دیتابیس این سایت هنوز تنظیم نشده است",
        )

    # پیش‌فرض سال/ماه: ماه شمسی جاری
    if year is None or month is None:
        current_year, current_month = get_current_jalali_year_month()
        year = year or current_year
        month = month or current_month

    # لایه‌ی مرخصی/ماموریت/تعطیل/غیبت (overlay کارا) فقط وقتی فعال است که
    # جدول‌هایش در نگاشت تردد/مرخصی این سایت تعریف شده باشند
    leave_mapping = (
        await db.execute(select(LeaveRequestMapping).where(LeaveRequestMapping.site_id == employee.site_id))
    ).scalar_one_or_none()
    kara_names = KaraNames(leave_mapping, mapping)
    if not kara_attendance_overlay.is_enabled(kara_names):
        kara_names = None  # None یعنی overlay غیرفعال
    type_titles: dict[int, str] = {}  # card_no -> عنوان نوع مرخصی
    # عنوان انواع مرخصی سایت برای نمایش در گزارش (اولین عنوان هر card_no)
    if kara_names is not None:
        types = (
            await db.execute(select(LeaveRequestType).where(LeaveRequestType.site_id == employee.site_id))
        ).scalars().all()
        for leave_type in types:
            if leave_type.card_no is not None and leave_type.card_no not in type_titles:
                type_titles[leave_type.card_no] = leave_type.title

    # خواندن گزارش از SQL Server سایت؛ خطای اتصال/کوئری به 502 تبدیل می‌شود
    try:
        return await get_monthly_attendance(
            site_connection,
            mapping,
            personnel_code=employee.personnel_code,
            year=year,
            month=month,
            kara_names=kara_names,
            type_titles=type_titles,
            branch_value=await get_site_branch_value(db, employee.site_id),
        )
    except MonthlyAttendanceError as e:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=str(e))
