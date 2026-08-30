"""
سرویس «گزارش تردد ماهانه» — از دستگاه‌های حضور و غیاب واقعی هر Site
می‌خواند، از همان SQL Server که برای Sync پرسنل هم استفاده می‌شود
(SiteConnection). نام جدول/ستون‌ها هاردکد نیستند - از یک AttendanceMapping
(دقیقاً همان الگوی EmployeeMapping برای Sync پرسنل) خوانده می‌شوند که
از پنل «تنظیمات سایت» قابل‌تنظیم است.

⚠️ طبق درخواست صریح: این سرویس داده خام را دقیقاً همان‌طور که در دیتابیس
ثبت شده، بدون هیچ پردازش/گروه‌بندی/جفت‌کردن اضافه‌ای نشان می‌دهد - فقط
بر اساس همان ستون Date خام دستگاه گروه‌بندی می‌شود (نه یک «روز شیفت»
محاسبه‌شده). به‌جای «ورود/خروج» (که فرض می‌کرد رکورد اول = ورود، دوم =
خروج)، هر تردد فقط با شماره ترتیبی («تردد ۱»، «تردد ۲»، ...) نمایش داده
می‌شود - همان داده خام، فقط با برچسب خنثی‌تر.

⚠️ زنده - این داده هیچ‌جا Cache/ذخیره نمی‌شود؛ هر بار درخواست، مستقیماً
از SQL Server سایت خوانده و بلافاصله نمایش داده می‌شود (کاملاً مستقل از
Sync Engine که پرسنل را به‌صورت دوره‌ای در دیتابیس خودِ پرتال ذخیره می‌کند).

⚠️ امنیتی: personnel_code همیشه از خودِ Employee کاربر لاگین‌شده خوانده
می‌شود (هرگز از ورودی درخواست). مقادیر (نه نام جدول/ستون) همیشه
Parameterized هستند؛ نام جدول/ستون فقط از AttendanceMapping (تنظیم‌شده
توسط Admin با مجوز sites.manage) می‌آیند و با [براکت] کوته می‌شوند —
همان الگوی Sync Engine (app/sync_engine/adapters/mssql_adapter.py).
"""
from __future__ import annotations

import asyncio
import logging

import pymssql

from app.core.persian_date import jalali_year_month_to_yyyymmdd_range
from app.core.security import decrypt_secret
from app.models.site import AttendanceMapping, DbType, SiteConnection

logger = logging.getLogger("faipco.monthly_attendance")


class MonthlyAttendanceError(Exception):
    pass


def _format_time(raw_time: int) -> str:
    """
    عدد فشرده ساعت (بدون جداکننده) را به HH:MM تبدیل می‌کند. 3 رقمی
    (مثلاً 618) -> 06:18؛ 4 رقمی (مثلاً 1401) -> 14:01.
    """
    s = str(raw_time)
    if len(s) == 3:
        hour, minute = s[0], s[1:3]
    elif len(s) == 4:
        hour, minute = s[0:2], s[2:4]
    elif len(s) <= 2:
        hour, minute = "0", s.zfill(2)
    else:
        return s
    return f"{int(hour):02d}:{minute}"


def _format_jalali_date(yyyymmdd: int) -> str:
    """14050524 -> "1405/05/24" """
    s = str(yyyymmdd)
    return f"{s[0:4]}/{s[4:6]}/{s[6:8]}"


def _connect(conn: SiteConnection) -> "pymssql.Connection":
    if conn.db_type != DbType.mssql:
        raise MonthlyAttendanceError("گزارش تردد ماهانه فقط برای اتصال از نوع SQL Server پشتیبانی می‌شود")
    return pymssql.connect(
        server=conn.host,
        port=str(conn.port),
        database=conn.database_name,
        user=conn.username,
        password=decrypt_secret(conn.password_encrypted),
        timeout=10,
        login_timeout=10,
    )


def _fetch_raw_rows_sync(
    conn: SiteConnection, mapping: AttendanceMapping, emp_no: int, from_date: int, to_date: int
) -> list[dict]:
    """
    نام جدول/ستون‌ها (فقط از AttendanceMapping تنظیم‌شده توسط Admin) با
    [براکت] در متن Query قرار می‌گیرند - SQL Server اجازه
    Parameterized-کردن نام جدول/ستون را نمی‌دهد. مقادیر واقعی
    (emp_no/from_date/to_date) همیشه Parameterized هستند.
    """
    connection = _connect(conn)
    try:
        query = f"""
            SELECT [{mapping.date_column}] AS AttendanceDate, [{mapping.time_column}] AS AttendanceTime
            FROM [{mapping.table_name}]
            WHERE [{mapping.personnel_code_column}] = %(emp_no)s
              AND [{mapping.date_column}] BETWEEN %(from_date)s AND %(to_date)s
            ORDER BY [{mapping.date_column}] ASC, [{mapping.time_column}] ASC
        """  # noqa: S608 - نام جدول/ستون فقط از تنظیمات Admin می‌آید
        with connection.cursor(as_dict=True) as cur:
            cur.execute(query, {"emp_no": emp_no, "from_date": from_date, "to_date": to_date})
            return list(cur.fetchall())
    finally:
        connection.close()


def _fetch_holidays_sync(conn: SiteConnection, mapping: AttendanceMapping, year: int, month: int) -> set[int]:
    """
    فهرست شماره روزهای تعطیل این ماه شمسی را از جدول تقویم برمی‌گرداند —
    یک ستون غیرصفر (طبق داده واقعی: 500 یا 501) یعنی آن روز تعطیل است؛
    فقط اگر همه فیلدهای نگاشت تقویم برای این سایت تنظیم شده باشند، وگرنه
    مجموعه خالی (بدون رنگ‌آمیزی تعطیلات — نه خطا).
    """
    if not (
        mapping.calendar_table_name
        and mapping.calendar_year_column
        and mapping.calendar_month_column
        and mapping.calendar_day_column_prefix
    ):
        return set()

    day_columns_sql = ", ".join(f"[{mapping.calendar_day_column_prefix}{i}]" for i in range(1, 32))
    connection = _connect(conn)
    try:
        query = f"""
            SELECT {day_columns_sql}
            FROM [{mapping.calendar_table_name}]
            WHERE [{mapping.calendar_year_column}] = %(year)s AND [{mapping.calendar_month_column}] = %(month)s
        """  # noqa: S608 - نام جدول/ستون فقط از تنظیمات Admin می‌آید
        with connection.cursor(as_dict=True) as cur:
            cur.execute(query, {"year": year, "month": month})
            row = cur.fetchone()
    finally:
        connection.close()

    if row is None:
        return set()

    holidays = set()
    for i in range(1, 32):
        value = row.get(f"{mapping.calendar_day_column_prefix}{i}")
        if value is not None and value != 0:
            holidays.add(i)
    return holidays


async def get_monthly_attendance(
    site_connection: SiteConnection,
    mapping: AttendanceMapping,
    *,
    personnel_code: str,
    year: int,
    month: int,
) -> dict:
    """
    گزارش تردد ماهانه یک پرسنل مشخص - داده خام، دقیقاً همان‌طور که در
    دیتابیس ثبت شده، فقط بر اساس ستون Date خام دستگاه گروه‌بندی شده
    (بدون هیچ تغییر/ترکیب/جفت‌کردن) - شامل روزهای بدون رکورد (با
    transits خالی).
    """
    try:
        emp_no = int(personnel_code)
    except (TypeError, ValueError):
        raise MonthlyAttendanceError("کد پرسنلی این کاربر عددی نیست — با فرمت مورد انتظار این گزارش سازگار نیست")

    from_date, to_date = jalali_year_month_to_yyyymmdd_range(year, month)

    try:
        raw_rows = await asyncio.to_thread(_fetch_raw_rows_sync, site_connection, mapping, emp_no, from_date, to_date)
    except MonthlyAttendanceError:
        raise
    except Exception as e:  # noqa: BLE001 - خطای اتصال/کوئری نباید کل درخواست را با 500 خام بترکاند
        logger.exception("خطا در دریافت گزارش تردد ماهانه (Emp_No=%s)", emp_no)
        raise MonthlyAttendanceError("اتصال به سیستم تردد ناموفق بود — لطفاً بعداً دوباره تلاش کنید") from e

    # ⚠️ شکست در خواندن تقویم/تعطیلات نباید کل گزارش تردد را خراب کند —
    # این یک قابلیت مکمل/اختیاری است، نه بخش اصلی گزارش.
    try:
        holidays = await asyncio.to_thread(_fetch_holidays_sync, site_connection, mapping, year, month)
    except Exception:  # noqa: BLE001
        logger.exception("خطا در دریافت تقویم/تعطیلات ماهانه (سایت=%s)", site_connection.site_id)
        holidays = set()

    # گروه‌بندی دقیقاً بر اساس همان ستون Date خام دستگاه - بدون هیچ تغییر
    rows_by_date: dict[int, list[dict]] = {}
    for row in raw_rows:
        rows_by_date.setdefault(row["AttendanceDate"], []).append(row)

    days_in_month = to_date % 100  # همان عدد روز از خودِ to_date (چون to_date = آخرین روز واقعی ماه است)
    max_transits = 0
    days_out = []

    for day in range(1, days_in_month + 1):
        date_int = year * 10000 + month * 100 + day
        day_rows = rows_by_date.get(date_int, [])
        transits = [_format_time(r["AttendanceTime"]) for r in day_rows]
        max_transits = max(max_transits, len(transits))
        days_out.append(
            {"date": _format_jalali_date(date_int), "day": day, "transits": transits, "is_holiday": day in holidays}
        )

    return {"year": year, "month": month, "max_transits_in_month": max_transits, "days": days_out}
