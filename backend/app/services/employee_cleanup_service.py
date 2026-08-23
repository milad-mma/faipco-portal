"""
پاک‌سازی پرسنل غیرفعالِ «بدون سابقه» — کسانی که is_active=False هستند و
هیچ ردی از استفاده واقعی از پرتال ندارند (نه فیش حقوقی، نه فیش کارکرد، نه
ورود/خروج GPS، نه Session آنلاین، نه حساب کاربری فعال‌شده، نه خواندن هیچ
اطلاعیه‌ای) — یعنی احتمالاً هرگز واقعاً فعال نبوده‌اند، فقط قبل از رفع باگ
Sync (نگاه کنید docs/sync-engine.md) اشتباهاً Import شده بودند.

⚠️ پرسنلی که حتی یک نشانه از فعالیت واقعی داشته باشد (مثلاً یک فیش حقوقی
قدیمی)، هرگز توسط این ابزار حذف نمی‌شود — دقیقاً طبق همان قانونی که برای
خودِ منطق Sync هم رعایت شد: کسی که واقعاً یک‌بار فعال بوده، سوابقش همیشه
حفظ می‌شود.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.attendance_card_receipt import AttendanceCardReceipt
from app.models.employee import Employee
from app.models.gps_activity_log import GpsActivityLog
from app.models.notice_read import NoticeRead
from app.models.payroll_receipt import PayrollReceipt
from app.models.presence_session import PresenceSession
from app.models.user import User


def _orphaned_inactive_query():
    """
    Employee هایی که is_active=False هستند و هیچ‌کدام از این نشانه‌های
    فعالیت واقعی را ندارند — به‌عنوان یک تابع مستقل نوشته شده تا هم
    Preview (شمارش/لیست) و هم Execute (حذف واقعی) دقیقاً از یک منطق مشترک
    استفاده کنند، بدون ریسک ناهم‌خوانی بین این دو.
    """
    has_payroll = select(PayrollReceipt.id).where(PayrollReceipt.employee_id == Employee.id).exists()
    has_attendance_card = (
        select(AttendanceCardReceipt.id).where(AttendanceCardReceipt.employee_id == Employee.id).exists()
    )
    has_gps_log = select(GpsActivityLog.id).where(GpsActivityLog.employee_id == Employee.id).exists()
    has_presence = select(PresenceSession.id).where(PresenceSession.employee_id == Employee.id).exists()
    # حساب کاربری با رمز عبور اختصاصی یعنی حداقل یک‌بار واقعاً وارد پرتال
    # شده و رمز پیش‌فرض (کد ملی) را عوض کرده — نشانه قوی از استفاده واقعی
    has_custom_password_user = (
        select(User.id)
        .where(User.employee_id == Employee.id, User.has_custom_password.is_(True))
        .exists()
    )
    has_read_notice = (
        select(NoticeRead.id)
        .join(User, User.id == NoticeRead.user_id)
        .where(User.employee_id == Employee.id)
        .exists()
    )

    return select(Employee).where(
        Employee.is_active.is_(False),
        ~has_payroll,
        ~has_attendance_card,
        ~has_gps_log,
        ~has_presence,
        ~has_custom_password_user,
        ~has_read_notice,
    )


async def find_orphaned_inactive_employees(db: AsyncSession) -> list[Employee]:
    result = await db.execute(_orphaned_inactive_query())
    return list(result.scalars().all())


async def delete_orphaned_inactive_employees(db: AsyncSession) -> int:
    """
    حذف واقعی — فقط بعد از این‌که Admin از پنل، گزارش Preview را دیده و
    صریحاً تأیید کرده باشد (نگاه کنید Endpoint در employees.py). چون همه
    این پرسنل طبق تعریف بالا هیچ رکورد وابسته‌ای ندارند، حذفشان هیچ داده
    تاریخی/مالی را از بین نمی‌برد.
    """
    employees = await find_orphaned_inactive_employees(db)
    count = len(employees)
    for employee in employees:
        await db.delete(employee)
    await db.commit()
    return count
