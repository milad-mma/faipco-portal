"""
پاک‌سازی پرسنل غیرفعالِ «بدون سابقه»: کسانی که is_active=False هستند و
هیچ ردی از استفاده واقعی از پرتال ندارند (نه فیش حقوقی، نه فیش کارکرد، نه
ورود/خروج GPS، نه Session آنلاین، نه حساب کاربری با رمز اختصاصی، نه خواندن
هیچ اطلاعیه‌ای).

پرسنلی که حتی یک نشانه از فعالیت واقعی داشته باشد (مثلاً یک فیش حقوقی
قدیمی)، هرگز توسط این ابزار حذف نمی‌شود؛ سوابق کسی که یک‌بار فعال بوده
همیشه حفظ می‌شود (همان قاعده‌ای که Sync Engine هم رعایت می‌کند).
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
    Query انتخاب Employee هایی که is_active=False هستند و هیچ نشانه فعالیت واقعی ندارند.
    هم Preview (شمارش/لیست) و هم حذف واقعی از همین تابع استفاده می‌کنند تا منطقشان یکسان بماند.
    """
    # زیرکوئری‌های EXISTS برای هر نوع سابقه فعالیت
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
    # خواندن اطلاعیه از طریق User متصل به این پرسنل بررسی می‌شود
    has_read_notice = (
        select(NoticeRead.id)
        .join(User, User.id == NoticeRead.user_id)
        .where(User.employee_id == Employee.id)
        .exists()
    )

    # غیرفعال و بدون هیچ‌کدام از سوابق بالا
    return select(Employee).where(
        Employee.is_active.is_(False),
        ~has_payroll,
        ~has_attendance_card,
        ~has_gps_log,
        ~has_presence,
        ~has_custom_password_user,
        ~has_read_notice,
    )


async def find_orphaned_inactive_employees(db: AsyncSession, site_ids: set[int] | None = None) -> list[Employee]:
    """
    فهرست پرسنل غیرفعال بدون سابقه را برمی‌گرداند (برای Preview پیش از حذف).
    site_ids: فقط پرسنل این سایت‌ها (None = همه‌ی سایت‌ها).
    """
    query = _orphaned_inactive_query()
    if site_ids is not None:
        query = query.where(Employee.site_id.in_(site_ids))
    result = await db.execute(query)
    return list(result.scalars().all())


async def delete_orphaned_inactive_employees(db: AsyncSession, site_ids: set[int] | None = None) -> int:
    """
    پرسنل غیرفعال بدون سابقه را واقعاً حذف می‌کند و تعدادشان را برمی‌گرداند.
    فقط پس از دیدن Preview و تأیید صریح Admin صدا زده می‌شود (Endpoint مربوط در employees.py).
    چون این پرسنل هیچ رکورد وابسته‌ای ندارند، حذفشان داده تاریخی/مالی را از بین نمی‌برد.
    """
    employees = await find_orphaned_inactive_employees(db, site_ids)
    count = len(employees)
    for employee in employees:
        await db.delete(employee)
    await db.commit()
    return count
