"""
سرویس «گزارش تردد ماهانه» — از دستگاه‌های حضور و غیاب واقعی هر Site
می‌خواند، از همان دیتابیس که برای Sync پرسنل هم استفاده می‌شود
(SiteConnection - از هر سه نوع پشتیبانی‌شده در این پروژه: SQL Server،
MySQL، PostgreSQL). نام جدول/ستون‌ها هاردکد نیستند - از یک AttendanceMapping
(دقیقاً همان الگوی EmployeeMapping برای Sync پرسنل) خوانده می‌شوند که
از پنل «تنظیمات سایت» قابل‌تنظیم است.

⚠️ طبق درخواست صریح: این سرویس داده خام را دقیقاً همان‌طور که در دیتابیس
ثبت شده، بدون هیچ پردازش/گروه‌بندی/جفت‌کردن اضافه‌ای نشان می‌دهد - فقط
بر اساس همان ستون Date خام دستگاه گروه‌بندی می‌شود (نه یک «روز شیفت»
محاسبه‌شده). به‌جای «ورود/خروج» (که فرض می‌کرد رکورد اول = ورود، دوم =
خروج)، هر تردد فقط با شماره ترتیبی («تردد ۱»، «تردد ۲»، ...) نمایش داده
می‌شود - همان داده خام، فقط با برچسب خنثی‌تر.

⚠️ زنده - این داده هیچ‌جا Cache/ذخیره نمی‌شود؛ هر بار درخواست، مستقیماً
از دیتابیس اصلی سایت خوانده و بلافاصله نمایش داده می‌شود (کاملاً مستقل
از Sync Engine که پرسنل را به‌صورت دوره‌ای در دیتابیس خودِ پرتال ذخیره
می‌کند).

⚠️ امنیتی: personnel_code همیشه از خودِ Employee کاربر لاگین‌شده خوانده
می‌شود (هرگز از ورودی درخواست). مقادیر (نه نام جدول/ستون) همیشه
Parameterized هستند؛ نام جدول/ستون فقط از AttendanceMapping (تنظیم‌شده
توسط Admin با مجوز sites.manage) می‌آیند و با علامت کوته مخصوص همان نوع
دیتابیس (تابع _quote) احاطه می‌شوند — همان الگوی امنیتی Sync Engine
(app/sync_engine/adapters/).
"""
from __future__ import annotations

import asyncio
import logging

import pymssql
import pymysql
import pymysql.cursors
import psycopg2
import psycopg2.extras

from app.core.persian_date import jalali_weekday_name, jalali_year_month_to_yyyymmdd_range
from app.core.security import decrypt_secret
from app.models.site import AttendanceMapping, AttendanceMappingMode, DbType, SiteConnection
from app.services import kara_attendance_overlay

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


def _minutes_between(start: int | None, end: int | None) -> int | None:
    """فاصله دو ساعت فشرده HHMM به دقیقه (None اگر یکی نامعلوم یا ترتیب نادرست باشد)."""
    if start is None or end is None:
        return None
    diff = (end // 100 * 60 + end % 100) - (start // 100 * 60 + start % 100)
    return diff if diff > 0 else None


def _today_jalali_int() -> int:
    """امروزِ شمسی (به وقت ایران) به فرمت فشرده YYYYMMDD."""
    import jdatetime
    from datetime import datetime
    from zoneinfo import ZoneInfo

    today = jdatetime.date.fromgregorian(date=datetime.now(ZoneInfo("Asia/Tehran")).date())
    return today.year * 10000 + today.month * 100 + today.day


def _format_jalali_date(yyyymmdd: int) -> str:
    """14050524 -> "1405/05/24" """
    s = str(yyyymmdd)
    return f"{s[0:4]}/{s[4:6]}/{s[6:8]}"


def _quote(db_type: DbType, name: str) -> str:
    """
    نام جدول/ستون (فقط از AttendanceMapping تنظیم‌شده توسط Admin، هرگز از
    ورودی کاربر نهایی) را با علامت کوته مخصوص همان نوع دیتابیس احاطه
    می‌کند - SQL Server از [براکت]، MySQL از بک‌تیک، PostgreSQL از
    گیومه دوتایی استفاده می‌کند؛ Parameterized-کردن نام جدول/ستون در
    هیچ‌کدام از این درایورها ممکن نیست (فقط مقادیر Parameterized می‌شوند).
    """
    if db_type == DbType.mysql:
        return f"`{name}`"
    if db_type == DbType.postgresql:
        return f'"{name}"'
    return f"[{name}]"  # mssql


def _connect(conn: SiteConnection):
    password = decrypt_secret(conn.password_encrypted)
    if conn.db_type == DbType.mssql:
        return pymssql.connect(
            server=conn.host,
            port=str(conn.port),
            database=conn.database_name,
            user=conn.username,
            password=password,
            timeout=10,
            login_timeout=10,
        )
    if conn.db_type == DbType.mysql:
        return pymysql.connect(
            host=conn.host,
            port=conn.port,
            database=conn.database_name,
            user=conn.username,
            password=password,
            connect_timeout=10,
            cursorclass=pymysql.cursors.DictCursor,
        )
    if conn.db_type == DbType.postgresql:
        return psycopg2.connect(
            host=conn.host,
            port=conn.port,
            dbname=conn.database_name,
            user=conn.username,
            password=password,
            connect_timeout=10,
        )
    raise MonthlyAttendanceError(f"نوع اتصال «{conn.db_type.value}» برای گزارش تردد ماهانه پشتیبانی نمی‌شود")


def _dict_cursor(connection, db_type: DbType):
    """
    ⚠️ فقط MSSQL/MySQL از پارامتر اختصاصی خودشان برای Cursor دیکشنری‌مانند
    استفاده می‌کنند (as_dict/cursorclass، که در _connect یا همین‌جا تنظیم
    شده)؛ PostgreSQL نیاز به cursor_factory جداگانه در لحظه ساخت Cursor دارد.
    """
    if db_type == DbType.mssql:
        return connection.cursor(as_dict=True)
    if db_type == DbType.postgresql:
        return connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    return connection.cursor()  # mysql - cursorclass از قبل روی خودِ Connection تنظیم شده


def _fetch_raw_rows_single_column_sync(
    conn: SiteConnection, mapping: AttendanceMapping, emp_no: int, from_date: int, to_date: int
) -> list[dict]:
    """
    فقط برای mapping_mode=single_column. نام جدول/ستون‌ها (فقط از
    AttendanceMapping تنظیم‌شده توسط Admin) با علامت کوته مخصوص نوع
    دیتابیس این سایت (_quote) در متن Query قرار می‌گیرند -
    Parameterized-کردن نام جدول/ستون در هیچ‌کدام از درایورها ممکن نیست.
    مقادیر واقعی (emp_no/from_date/to_date) همیشه Parameterized هستند.
    نام مستعار ستون‌ها (AS ...) هم عمداً کوته می‌شوند - وگرنه PostgreSQL
    آن‌ها را خودکار کوچک می‌کرد و کلید دیکشنری خروجی با آنچه کد زیر
    انتظار دارد ("AttendanceDate"/"AttendanceTime") مطابقت نمی‌داشت.

    خروجی: [{"AttendanceDate": int, "AttendanceTime": int}, ...]
    """
    q = lambda name: _quote(conn.db_type, name)  # noqa: E731
    connection = _connect(conn)
    try:
        query = f"""
            SELECT {q(mapping.date_column)} AS {q("AttendanceDate")}, {q(mapping.time_column)} AS {q("AttendanceTime")}
            FROM {q(mapping.table_name)}
            WHERE {q(mapping.personnel_code_column)} = %(emp_no)s
              AND {q(mapping.date_column)} BETWEEN %(from_date)s AND %(to_date)s
            ORDER BY {q(mapping.date_column)} ASC, {q(mapping.time_column)} ASC
        """  # noqa: S608 - نام جدول/ستون فقط از تنظیمات Admin می‌آید
        with _dict_cursor(connection, conn.db_type) as cur:
            cur.execute(query, {"emp_no": emp_no, "from_date": from_date, "to_date": to_date})
            return list(cur.fetchall())
    finally:
        connection.close()


def _fetch_raw_rows_enter_exit_sync(
    conn: SiteConnection, mapping: AttendanceMapping, emp_no: int, from_date: int, to_date: int
) -> list[dict]:
    """
    فقط برای mapping_mode=enter_exit_columns - هر ردیف یک نشست کامل است
    (نه یک تردد منفرد)، با چهار ستون جدا. یک نشست اگر یا تاریخ ورودش یا
    تاریخ خروجش داخل بازه ماه درخواستی باشد لحاظ می‌شود (نشستی که از یک
    روزِ خارج از بازه شروع شده ولی همین ماه پایان یافته، یا برعکس، هم
    باید دیده شود). exit_date/exit_time می‌توانند NULL باشند (نشست هنوز
    باز است).

    خروجی: [{"EnterDate": int, "EnterTime": int, "ExitDate": int|None, "ExitTime": int|None}, ...]
    """
    q = lambda name: _quote(conn.db_type, name)  # noqa: E731
    connection = _connect(conn)
    try:
        query = f"""
            SELECT {q(mapping.enter_date_column)} AS {q("EnterDate")}, {q(mapping.enter_time_column)} AS {q("EnterTime")},
                   {q(mapping.exit_date_column)} AS {q("ExitDate")}, {q(mapping.exit_time_column)} AS {q("ExitTime")}
            FROM {q(mapping.table_name)}
            WHERE {q(mapping.personnel_code_column)} = %(emp_no)s
              AND (
                    {q(mapping.enter_date_column)} BETWEEN %(from_date)s AND %(to_date)s
                    OR {q(mapping.exit_date_column)} BETWEEN %(from_date)s AND %(to_date)s
                  )
            ORDER BY {q(mapping.enter_date_column)} ASC, {q(mapping.enter_time_column)} ASC
        """  # noqa: S608 - نام جدول/ستون فقط از تنظیمات Admin می‌آید
        with _dict_cursor(connection, conn.db_type) as cur:
            cur.execute(query, {"emp_no": emp_no, "from_date": from_date, "to_date": to_date})
            return list(cur.fetchall())
    finally:
        connection.close()


def _normalize_enter_exit_sessions(sessions: list[dict]) -> list[dict]:
    """
    هر نشست (ورود+خروج) را به یک یا دو «تردد منفرد» تبدیل می‌کند - یکی
    برای لحظه ورود، و اگر خروج ثبت شده باشد (NULL نباشد)، یکی هم برای
    لحظه خروج؛ خروجی دقیقاً هم‌شکل با حالت single_column می‌شود
    (["AttendanceDate", "AttendanceTime"])، تا بقیه خط لوله (گروه‌بندی
    بر اساس روز، ساخت days_out) بدون هیچ تغییری برای هر دو حالت کار کند.
    """
    transits: list[dict] = []
    for session in sessions:
        if session.get("EnterDate") is not None and session.get("EnterTime") is not None:
            transits.append({"AttendanceDate": session["EnterDate"], "AttendanceTime": session["EnterTime"]})
        if session.get("ExitDate") is not None and session.get("ExitTime") is not None:
            transits.append({"AttendanceDate": session["ExitDate"], "AttendanceTime": session["ExitTime"]})
    return transits


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

    q = lambda name: _quote(conn.db_type, name)  # noqa: E731
    day_columns_sql = ", ".join(q(f"{mapping.calendar_day_column_prefix}{i}") for i in range(1, 32))
    connection = _connect(conn)
    try:
        query = f"""
            SELECT {day_columns_sql}
            FROM {q(mapping.calendar_table_name)}
            WHERE {q(mapping.calendar_year_column)} = %(year)s AND {q(mapping.calendar_month_column)} = %(month)s
        """  # noqa: S608 - نام جدول/ستون فقط از تنظیمات Admin می‌آید
        with _dict_cursor(connection, conn.db_type) as cur:
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
    kara_names=None,
    type_titles: dict[int, str] | None = None,
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
        if mapping.mapping_mode == AttendanceMappingMode.enter_exit_columns:
            sessions = await asyncio.to_thread(
                _fetch_raw_rows_enter_exit_sync, site_connection, mapping, emp_no, from_date, to_date
            )
            raw_rows = _normalize_enter_exit_sessions(sessions)
        else:
            raw_rows = await asyncio.to_thread(
                _fetch_raw_rows_single_column_sync, site_connection, mapping, emp_no, from_date, to_date
            )
    except MonthlyAttendanceError:
        raise
    except Exception as e:  # noqa: BLE001 - خطای اتصال/کوئری نباید کل درخواست را با 500 خام بترکاند
        logger.exception("خطا در دریافت گزارش تردد ماهانه (Emp_No=%s)", emp_no)
        raise MonthlyAttendanceError("اتصال به سیستم تردد با خطا مواجه شد — لطفاً بعداً دوباره تلاش کنید") from e

    # ⚠️ شکست در خواندن تقویم/تعطیلات نباید کل گزارش تردد را خراب کند —
    # این یک قابلیت مکمل/اختیاری است، نه بخش اصلی گزارش.
    try:
        holidays = await asyncio.to_thread(_fetch_holidays_sync, site_connection, mapping, year, month)
    except Exception:  # noqa: BLE001
        logger.exception("خطا در دریافت تقویم/تعطیلات ماهانه (سایت=%s)", site_connection.site_id)
        holidays = set()

    # ⚠️ لایه مرخصی/ماموریت (فقط کاراوب) - شکستش نباید گزارش اصلی را خراب کند
    overlay = None
    if kara_names is not None and site_connection.db_type == DbType.mssql:
        try:
            overlay = await asyncio.to_thread(
                kara_attendance_overlay.fetch_overlay_sync, site_connection, kara_names, emp_no, from_date, to_date
            )
        except Exception:  # noqa: BLE001
            logger.exception("خطا در دریافت مرخصی/ماموریت برای گزارش تردد (Emp_No=%s)", emp_no)
            overlay = None

    def _label(card_no: int) -> dict:
        card = (overlay or {}).get("cards", {}).get(card_no, {})
        # عنوان نوع درخواست تعریف‌شده در پرتال (خواناتر) مقدم است؛ در غیر
        # این صورت عنوان رسمی همان کارت در کاراوب
        title = (type_titles or {}).get(card_no) or card.get("title") or f"کد {card_no}"
        return {"code": card_no, "label": title, "kind": card.get("kind", kara_attendance_overlay.KIND_OTHER)}

    # گروه‌بندی دقیقاً بر اساس همان ستون Date خام دستگاه - بدون هیچ تغییر
    rows_by_date: dict[int, list[dict]] = {}
    for row in raw_rows:
        rows_by_date.setdefault(row["AttendanceDate"], []).append(row)

    def _mark(card_no: int, start: int | None, end: int | None) -> dict:
        mark = _label(card_no)
        mark["from"] = _format_time(start % 2400) if start is not None else None
        mark["to"] = _format_time(end % 2400) if end is not None else None
        mark["minutes"] = _minutes_between(start, end)
        return mark

    # ⚠️ علامت مرخصی/ماموریت ساعتی - دقیقاً مثل محاسبه کاراوب (کارکرد روزانه،
    # ستون S_Sha): تردد «ورود» (اول/سوم/...) یعنی از خروج قبلی یا شروع شیفت تا
    # همین تردد؛ تردد «خروج» (دوم/چهارم/...) یعنی از همین تردد تا ورود بعدی یا
    # پایان شیفت. ترتیب ورود/خروج از کارکرد روزانه کاراوب خوانده می‌شود تا شیفت
    # شب/گردشی (خروج بعد از نیمه‌شب که تاریخ روز بعد را دارد) هم درست باشد؛
    # علامت کارت (Status) همیشه از خودِ جدول تردد (زنده) خوانده می‌شود.
    shift_punch_marks: dict[tuple[int, int], dict | None] = {}
    shift_hourly: dict[int, list[dict]] = {}
    for shift_date, info in ((overlay or {}).get("shift_days") or {}).items():
        times = info["cards"]
        for index, kara_time in enumerate(times):
            actual_date = shift_date if kara_time < 2400 else kara_attendance_overlay.next_jalali_date(shift_date)
            actual_time = kara_time % 2400
            status_code = overlay["punch_status"].get((actual_date, actual_time))
            mark = None
            if status_code:
                start, end = kara_attendance_overlay.hourly_interval(times, index, info["bounds"])
                mark = _mark(status_code, start, end)
                shift_hourly.setdefault(shift_date, []).append(mark)
            shift_punch_marks[(actual_date, actual_time)] = mark

    today_int = _today_jalali_int()
    days_in_month = to_date % 100  # همان عدد روز از خودِ to_date (چون to_date = آخرین روز واقعی ماه است)
    max_transits = 0
    days_out = []

    for day in range(1, days_in_month + 1):
        date_int = year * 10000 + month * 100 + day
        day_rows = rows_by_date.get(date_int, [])
        transits = [_format_time(r["AttendanceTime"]) for r in day_rows]
        max_transits = max(max_transits, len(transits))

        # ⚠️ علامت مرخصی/ماموریت ساعتی روی هر تردد - دقیقاً مثل محاسبه کاراوب
        # (کارکرد روزانه، ستون S_Sha): تردد «ورود» (اول/سوم/...) یعنی از خروج
        # قبلی یا شروع شیفت تا همین تردد؛ تردد «خروج» (دوم/چهارم/...) یعنی از
        # همین تردد تا ورود بعدی یا پایان شیفت. (قبلاً همیشه «از همین تردد تا
        # تردد بعدی» نمایش داده می‌شد - ورود ۰۸:۱۳ با کارت مرخصی به‌اشتباه
        # «۰۸:۱۳ تا ۱۴:۳۷» دیده می‌شد، در حالی که کاراوب ۰۶:۳۰ تا ۰۸:۱۳ حساب می‌کند.)
        transit_marks: list[dict | None] = []
        hourly: list[dict] = []
        daily_mark = None
        if overlay is not None:
            covered = all((date_int, t) in shift_punch_marks for t in (r["AttendanceTime"] for r in day_rows))
            if covered:
                # ترددهای این روز در کارکرد روزانه کاراوب شیفت‌بندی شده‌اند
                for r in day_rows:
                    mark = shift_punch_marks[(date_int, r["AttendanceTime"])]
                    transit_marks.append(mark)
                hourly.extend(shift_hourly.get(date_int, []))
            else:
                # هنوز در کارکرد روزانه محاسبه نشده - همان قاعده روی ترددهای خام همین تاریخ
                shift = (overlay.get("shift_times") or {}).get(date_int)
                times = [r["AttendanceTime"] for r in day_rows]
                for index, r in enumerate(day_rows):
                    status_code = overlay["punch_status"].get((date_int, r["AttendanceTime"]))
                    if not status_code:
                        transit_marks.append(None)
                        continue
                    start, end = kara_attendance_overlay.hourly_interval(times, index, shift)
                    mark = _mark(status_code, start, end)
                    transit_marks.append(mark)
                    hourly.append(mark)
            daily_code = overlay["daily"].get(date_int)
            if daily_code and day not in holidays:
                daily_mark = _label(daily_code)

        # ⚠️ برچسب وضعیت روز (طبق درخواست صریح کاربر):
        #   تعطیل  = تعطیل تقویمی یا روز غیرکاری شیفت خودِ فرد (کارکرد روزانه)
        #   غیبت   = روز کاری گذشته، بدون هیچ تردد و بدون مرخصی/ماموریت روزانه
        # امروز و روزهای آینده هرگز «غیبت» نمی‌گیرند.
        is_off = day in holidays or bool(overlay and overlay.get("work_calendar", {}).get(date_int))
        if is_off:
            day_status = "holiday"
        elif daily_mark is not None:
            day_status = daily_mark["kind"]
        elif overlay is not None and overlay.get("daily_enabled") and not transits and date_int < today_int:
            day_status = "absent"
        else:
            day_status = None

        days_out.append(
            {
                "date": _format_jalali_date(date_int),
                "day": day,
                "weekday": jalali_weekday_name(year, month, day),
                "transits": transits,
                "is_holiday": is_off,
                "day_status": day_status,
                "transit_marks": transit_marks,
                "hourly_absences": hourly,
                "daily_absence": daily_mark,
            }
        )

    return {"year": year, "month": month, "max_transits_in_month": max_transits, "days": days_out}
