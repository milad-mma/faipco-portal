"""
سرویس «گزارش تردد ماهانه» — از دستگاه‌های حضور و غیاب واقعی هر Site
می‌خواند، از همان SQL Server که برای Sync پرسنل هم استفاده می‌شود
(SiteConnection). نام جدول/ستون‌ها هاردکد نیستند - از یک AttendanceMapping
(دقیقاً همان الگوی EmployeeMapping برای Sync پرسنل) خوانده می‌شوند که
از پنل «تنظیمات سایت» قابل‌تنظیم است.

به‌جای «ورود/خروج» (که فرض می‌کرد رکورد اول هر روز = ورود، دوم = خروج)،
هر تردد فقط با شماره ترتیبی («تردد ۱»، «تردد ۲»، ...) نمایش داده می‌شود.

چرا «ساعت مرز شبانه‌روز کاری» ثابت کار نمی‌کرد: برای شرکت‌هایی که بازه
ورود/خروج شیفت‌های مختلف با هم همپوشانی دارند (مثلاً بازه خروج شیفت روز
14:00-18:30 با بازه ورود شیفت شب 18:00-20:00 همپوشانی دارد، یا بازه
خروج شیفت شب و بازه ورود شیفت روز هر دو دقیقاً 06:00-08:00 است)، هیچ
ساعت مرز ثابتی نمی‌تواند این‌ها را درست تفکیک کند.

راه‌حل واقعی: به‌جای تکیه به یک ساعت ثابت، ترددهای هر پرسنل بر اساس
ترتیب زمانی واقعی خودشان دو‌به‌دو جفت می‌شوند (تردد 1و2 یک جفت، 3و4
جفت بعدی، و به همین ترتیب) - مستقل از این‌که کدام ساعت از شبانه‌روز
است. «روز نمایش» هر جفت، روز تقویمی اولین تردد آن جفت است؛ یعنی یک
شیفت شب که از نیمه‌شب می‌گذرد (ورود امشب + خروج فردا صبح)، هر دو تردد
آن زیر همان «امشب» نمایش داده می‌شوند - نه به دو روز جدا تقسیم می‌شوند.
این روش کاملاً مستقل از برنامه شیفت است و برای هر الگویی (حتی اگر
ساعت کاری تغییر کند) درست کار می‌کند - تنها فرضش این است که دستگاه
همیشه ترددها را به تناوب (باز، بسته، باز، بسته) ثبت می‌کند.

محدودیت شناخته‌شده: اگر یک پرسنل یک روز فراموش کند تردد بزند (یک
رکورد از قلم بیفتد)، تناوب برای باقی آن بازه (تا رکورد بعدی) به‌هم
می‌خورد. این یک محدودیت ذاتی هر روش مبتنی بر تناوب است.

امنیتی: personnel_code همیشه از خودِ Employee کاربر لاگین‌شده خوانده
می‌شود (هرگز از ورودی درخواست). مقادیر (نه نام جدول/ستون) همیشه
Parameterized هستند.
"""
from __future__ import annotations

import asyncio
import logging

import pymssql

from app.core.persian_date import jalali_yyyymmdd_add_days, jalali_year_month_to_yyyymmdd_range
from app.core.security import decrypt_secret
from app.models.site import AttendanceMapping, DbType, SiteConnection

logger = logging.getLogger("faipco.monthly_attendance")

# چند روز اضافه، هر دو طرف بازه اصلی، برای گرفتن ترددهای مرزی و محاسبه
# صحیح تناوب (زوج/فرد) از یک نقطه معقول قبل از شروع بازه اصلی.
_BUFFER_DAYS = 3


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


async def get_monthly_attendance(
    site_connection: SiteConnection,
    mapping: AttendanceMapping,
    *,
    personnel_code: str,
    year: int,
    month: int,
) -> dict:
    """
    گزارش تردد ماهانه یک پرسنل مشخص - ساختار «روز + فهرست ترددهای پویا»،
    شامل روزهای بدون رکورد (با transits خالی).
    """
    try:
        emp_no = int(personnel_code)
    except (TypeError, ValueError):
        raise MonthlyAttendanceError("کد پرسنلی این کاربر عددی نیست — با فرمت مورد انتظار این گزارش سازگار نیست")

    from_date, to_date = jalali_year_month_to_yyyymmdd_range(year, month)
    query_from_date = jalali_yyyymmdd_add_days(from_date, -_BUFFER_DAYS)
    query_to_date = jalali_yyyymmdd_add_days(to_date, _BUFFER_DAYS)

    try:
        raw_rows = await asyncio.to_thread(
            _fetch_raw_rows_sync, site_connection, mapping, emp_no, query_from_date, query_to_date
        )
    except MonthlyAttendanceError:
        raise
    except Exception as e:  # noqa: BLE001 - خطای اتصال/کوئری نباید کل درخواست را با 500 خام بترکاند
        logger.exception("خطا در دریافت گزارش تردد ماهانه (Emp_No=%s)", emp_no)
        raise MonthlyAttendanceError("اتصال به سیستم تردد ناموفق بود — لطفاً بعداً دوباره تلاش کنید") from e

    # مرتب‌سازی زمانی کامل (نه فقط بر اساس Time، چون بازه شامل چند روز
    # تقویمی است) - این ترتیب واقعی است که تناوب زوج/فرد بر اساس آن حساب می‌شود.
    raw_rows.sort(key=lambda r: (r["AttendanceDate"], r["AttendanceTime"]))

    # جفت‌کردن دوبه‌دو بر اساس ترتیب (نه ساعت ثابت) - عضو اول هر جفت،
    # «روز نمایش» کل آن جفت را تعیین می‌کند.
    rows_by_display_date: dict[int, list[dict]] = {}
    for i in range(0, len(raw_rows), 2):
        pair = raw_rows[i : i + 2]
        display_date = pair[0]["AttendanceDate"]
        rows_by_display_date.setdefault(display_date, []).extend(pair)

    days_in_month = to_date % 100  # همان عدد روز از خودِ to_date (چون to_date = آخرین روز واقعی ماه است)
    max_transits = 0
    days_out = []

    for day in range(1, days_in_month + 1):
        date_int = year * 10000 + month * 100 + day
        day_rows = rows_by_display_date.get(date_int, [])
        transits = [_format_time(r["AttendanceTime"]) for r in day_rows]
        max_transits = max(max_transits, len(transits))
        days_out.append({"date": _format_jalali_date(date_int), "day": day, "transits": transits})

    return {"year": year, "month": month, "max_transits_in_month": max_transits, "days": days_out}
