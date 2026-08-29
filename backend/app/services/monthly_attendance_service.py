"""
سرویس «گزارش تردد ماهانه» — از دستگاه‌های حضور و غیاب واقعی هر Site
می‌خواند، از همان SQL Server که برای Sync پرسنل هم استفاده می‌شود
(SiteConnection). نام جدول/ستون‌ها هاردکد نیستند — چون نرم‌افزارهای
مختلف حضور و غیاب دستگاهی، نام جدول/ستون‌های متفاوتی دارند، از یک
AttendanceMapping (دقیقاً همان الگوی EmployeeMapping برای Sync پرسنل)
خوانده می‌شوند که از پنل «تنظیمات سایت» قابل‌تنظیم است.

⚠️ رفتار ورود/خروج کاملاً بر اساس ترتیب زمانی است، نه یک ستون مشخص:
رکورد اول هر روز = ورود، دوم = خروج، سوم = ورود، و به همین ترتیب
(تناوب فرد/زوج) — چون در داده‌های واقعی، ستونی که جهت تردد را مشخص کند
همیشه معنای قابل‌اعتمادی ندارد.

⚠️ امنیتی: personnel_code همیشه از خودِ Employee کاربر لاگین‌شده خوانده
می‌شود (هرگز از ورودی درخواست) — به عهده‌ی Endpoint (نه این سرویس) است
که این را تضمین کند. مقادیر (نه نام جدول/ستون) همیشه Parameterized
هستند. نام جدول/ستون فقط از AttendanceMapping (تنظیم‌شده توسط Admin با
مجوز sites.manage) می‌آیند و با [براکت] کوته می‌شوند — دقیقاً همان الگوی
استفاده‌شده در Sync Engine (app/sync_engine/adapters/mssql_adapter.py)
برای همین نوع نیاز.
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
    عدد فشرده ساعت (بدون جداکننده، بدون صفر ابتدایی) را به HH:MM تبدیل
    می‌کند. اگر ۳ رقمی بود (مثلاً 618)، رقم اول ساعت و دو رقم بعد دقیقه
    است (06:18)؛ اگر ۴ رقمی بود (مثلاً 1401)، دو رقم اول ساعت و دو رقم
    بعد دقیقه است (14:01).
    """
    s = str(raw_time)
    if len(s) == 3:
        hour, minute = s[0], s[1:3]
    elif len(s) == 4:
        hour, minute = s[0:2], s[2:4]
    elif len(s) <= 2:
        # حالت لبه‌ای: فقط دقیقه (کمتر از ساعت ۱، مثلاً ساعت ۰۰:۰۵ → عدد 5)
        hour, minute = "0", s.zfill(2)
    else:
        # مقدار غیرمنتظره — به‌جای شکستن کل گزارش، همان رشته خام برگردانده می‌شود
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
    ⚠️ نام جدول/ستون‌ها (که فقط از AttendanceMapping تنظیم‌شده توسط Admin
    می‌آیند، نه از ورودی کاربر عادی) با [براکت] در متن Query قرار
    می‌گیرند — SQL Server اجازه Parameterized-کردن نام جدول/ستون را
    نمی‌دهد (فقط مقادیر). مقادیر واقعی (emp_no/from_date/to_date) همیشه
    Parameterized هستند — همان چیزی که واقعاً جلوی SQL Injection را
    می‌گیرد.
    """
    connection = _connect(conn)
    try:
        query = f"""
            SELECT
                [{mapping.date_column}] AS AttendanceDate,
                [{mapping.time_column}] AS AttendanceTime,
                ROW_NUMBER() OVER (
                    PARTITION BY [{mapping.date_column}] ORDER BY [{mapping.time_column}]
                ) AS Seq
            FROM [{mapping.table_name}]
            WHERE [{mapping.personnel_code_column}] = %(emp_no)s
              AND [{mapping.date_column}] BETWEEN %(from_date)s AND %(to_date)s
            ORDER BY [{mapping.date_column}] ASC, [{mapping.time_column}] ASC
        """  # noqa: S608 - نام جدول/ستون فقط از تنظیمات Admin می‌آید، نه ورودی کاربر
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
    گزارش تردد ماهانه یک پرسنل مشخص - ساختار «روز + ستون‌های ورود/خروج
    پویا»، شامل روزهای بدون رکورد (با Pairs خالی).
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

    # گروه‌بندی بر اساس روز، و تبدیل هر رکورد به یک عضو از یک جفت (ورود/خروج)
    rows_by_date: dict[int, list[dict]] = {}
    for row in raw_rows:
        rows_by_date.setdefault(row["AttendanceDate"], []).append(row)

    days_in_month = to_date % 100  # همان عدد روز از خودِ to_date (چون to_date = آخرین روز واقعی ماه است)
    max_pairs = 0
    days_out = []

    for day in range(1, days_in_month + 1):
        date_int = year * 10000 + month * 100 + day
        day_rows = rows_by_date.get(date_int, [])
        pairs = []
        for i in range(0, len(day_rows), 2):
            entry_row = day_rows[i]
            exit_row = day_rows[i + 1] if i + 1 < len(day_rows) else None
            pairs.append(
                {
                    "entry": _format_time(entry_row["AttendanceTime"]),
                    "exit": _format_time(exit_row["AttendanceTime"]) if exit_row else None,
                }
            )
        max_pairs = max(max_pairs, len(pairs))
        days_out.append({"date": _format_jalali_date(date_int), "day": day, "pairs": pairs})

    return {"year": year, "month": month, "max_pairs_in_month": max_pairs, "days": days_out}
