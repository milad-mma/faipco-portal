"""
سرویس «گزارش تردد ماهانه» — می‌خواند از جدول DataFile نرم‌افزار «کاراوب»
(Kara WorkFlow)، دقیقاً در همان SQL Server هر Site که برای Sync پرسنل هم
استفاده می‌شود (SiteConnection). فقط برای Siteهایی که kara_workflow_enabled
روشن است معنا دارد.

⚠️ رفتار ورود/خروج کاملاً بر اساس ترتیب زمانی است، نه یک ستون مشخص:
رکورد اول هر روز = ورود، دوم = خروج، سوم = ورود، و به همین ترتیب
(تناوب فرد/زوج) — چون ستون Direction در داده واقعی همیشه ثابت (۰) است
و معنای ورود/خروج را مشخص نمی‌کند.

⚠️ امنیتی: Emp_No همیشه از خودِ Employee کاربر لاگین‌شده خوانده می‌شود
(هرگز از ورودی درخواست) — به عهده‌ی Endpoint (نه این سرویس) است که این
را تضمین کند؛ این سرویس فقط personnel_code‌ای را که به آن داده شده
پرس‌وجو می‌کند.
"""
from __future__ import annotations

import asyncio
import logging

import pymssql

from app.core.persian_date import jalali_year_month_to_yyyymmdd_range
from app.core.security import decrypt_secret
from app.models.site import DbType, SiteConnection

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
        raise MonthlyAttendanceError(
            "گزارش تردد ماهانه فقط برای اتصال از نوع SQL Server (کاراوب) پشتیبانی می‌شود"
        )
    return pymssql.connect(
        server=conn.host,
        port=str(conn.port),
        database=conn.database_name,
        user=conn.username,
        password=decrypt_secret(conn.password_encrypted),
        timeout=10,
        login_timeout=10,
    )


def _fetch_raw_rows_sync(conn: SiteConnection, emp_no: int, from_date: int, to_date: int) -> list[dict]:
    """
    Parameterized Query - emp_no/from_date/to_date همیشه به‌صورت پارامتر
    (نه رشته‌سازی مستقیم در متن SQL) فرستاده می‌شوند، دقیقاً برای
    جلوگیری از SQL Injection.
    """
    connection = _connect(conn)
    try:
        query = """
            SELECT
                [Date],
                [Time],
                ROW_NUMBER() OVER (PARTITION BY [Date] ORDER BY [Time]) AS Seq
            FROM [DataFile]
            WHERE [Emp_No] = %(emp_no)s
              AND [Date] BETWEEN %(from_date)s AND %(to_date)s
            ORDER BY [Date] ASC, [Time] ASC
        """
        with connection.cursor(as_dict=True) as cur:
            cur.execute(query, {"emp_no": emp_no, "from_date": from_date, "to_date": to_date})
            return list(cur.fetchall())
    finally:
        connection.close()


async def get_monthly_attendance(
    site_connection: SiteConnection, *, personnel_code: str, year: int, month: int
) -> dict:
    """
    گزارش تردد ماهانه یک پرسنل مشخص - ساختار «روز + ستون‌های ورود/خروج
    پویا»، شامل روزهای بدون رکورد (با Pairs خالی).
    """
    try:
        emp_no = int(personnel_code)
    except (TypeError, ValueError):
        raise MonthlyAttendanceError(
            "کد پرسنلی این کاربر عددی نیست — با فرمت Emp_No نرم‌افزار کاراوب سازگار نیست"
        )

    from_date, to_date = jalali_year_month_to_yyyymmdd_range(year, month)

    try:
        raw_rows = await asyncio.to_thread(_fetch_raw_rows_sync, site_connection, emp_no, from_date, to_date)
    except MonthlyAttendanceError:
        raise
    except Exception as e:  # noqa: BLE001 - خطای اتصال/کوئری نباید کل درخواست را با 500 خام بترکاند
        logger.exception("خطا در دریافت گزارش تردد ماهانه از کاراوب (Emp_No=%s)", emp_no)
        raise MonthlyAttendanceError("اتصال به سیستم تردد کاراوب ناموفق بود — لطفاً بعداً دوباره تلاش کنید") from e

    # گروه‌بندی بر اساس روز، و تبدیل هر رکورد به یک عضو از یک جفت (ورود/خروج)
    rows_by_date: dict[int, list[dict]] = {}
    for row in raw_rows:
        rows_by_date.setdefault(row["Date"], []).append(row)

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
                    "entry": _format_time(entry_row["Time"]),
                    "exit": _format_time(exit_row["Time"]) if exit_row else None,
                }
            )
        max_pairs = max(max_pairs, len(pairs))
        days_out.append({"date": _format_jalali_date(date_int), "day": day, "pairs": pairs})

    return {"year": year, "month": month, "max_pairs_in_month": max_pairs, "days": days_out}
