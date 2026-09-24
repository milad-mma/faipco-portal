"""
سرویس «گزارش تردد ماهانه».

ترددهای یک پرسنل را در یک ماه شمسی از دیتابیس دستگاه حضور و غیاب سایت
(SiteConnection؛ SQL Server، MySQL یا PostgreSQL) می‌خواند و به‌صورت
روزبه‌روز برمی‌گرداند. نام جدول/ستون‌ها از AttendanceMapping (تنظیم‌شده در
پنل «تنظیمات سایت») خوانده می‌شود، نه هاردکد.

داده‌ی خام دقیقاً همان‌طور که در دیتابیس ثبت شده نمایش داده می‌شود: فقط بر
اساس ستون Date خام دستگاه گروه‌بندی می‌شود (نه «روز شیفت» محاسبه‌شده) و هر
تردد با شماره‌ی ترتیبی («تردد ۱»، «تردد ۲»، ...) می‌آید، نه برچسب ورود/خروج.
روی این داده، لایه‌ی اختیاری تعطیلات تقویمی و لایه‌ی کاراوب (مرخصی/ماموریت
ساعتی و روزانه، تقویم کاری شیفت، غیبت) قرار می‌گیرد.

داده‌ی خام فقط ۳۰ ثانیه در حافظه‌ی همان worker نگه داشته می‌شود (برای جابه‌جایی
داشبورد و صفحه‌ی گزارش) و سه منبع آن هم‌زمان خوانده می‌شوند؛ جدا از Sync Engine
که پرسنل را دوره‌ای در دیتابیس پرتال ذخیره می‌کند.

امنیت: personnel_code همیشه از Employee کاربر لاگین‌شده می‌آید. مقادیر
همیشه Parameterized هستند؛ نام جدول/ستون فقط از AttendanceMapping (تنظیم
Admin با مجوز sites.manage) می‌آید و با علامت کوته‌ی نوع دیتابیس (_quote)
احاطه می‌شود — همان الگوی app/sync_engine/adapters/.
"""
from __future__ import annotations

import asyncio
import logging
import time

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
    """خطای گزارش تردد با پیام فارسی قابل‌نمایش (کد پرسنلی نامعتبر، خطای اتصال، نوع دیتابیس پشتیبانی‌نشده)."""
    pass


def _format_time(raw_time: int) -> str:
    """
    عدد فشرده‌ی ساعت (بدون جداکننده) را به HH:MM تبدیل می‌کند.
    3 رقمی (618) -> 06:18؛ 4 رقمی (1401) -> 14:01؛ 1-2 رقمی -> 00:MM؛ طول دیگر بدون تغییر برمی‌گردد.
    """
    s = str(raw_time)
    # تفکیک ساعت/دقیقه بر اساس تعداد رقم
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
    """فاصله‌ی دو ساعت فشرده‌ی HHMM را به دقیقه برمی‌گرداند (None اگر یکی نامعلوم یا پایان قبل از شروع باشد)."""
    if start is None or end is None:
        return None
    # هر ساعت فشرده به دقیقه از نیمه‌شب تبدیل می‌شود
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
    """تاریخ شمسی فشرده را به رشته‌ی نمایشی تبدیل می‌کند: 14050524 -> "1405/05/24"."""
    s = str(yyyymmdd)
    return f"{s[0:4]}/{s[4:6]}/{s[6:8]}"


def _quote(db_type: DbType, name: str) -> str:
    """
    نام جدول/ستون را با علامت کوته‌ی مخصوص نوع دیتابیس احاطه می‌کند:
    SQL Server [براکت]، MySQL بک‌تیک، PostgreSQL گیومه‌ی دوتایی.
    نام‌ها فقط از AttendanceMapping تنظیم‌شده توسط Admin می‌آیند، چون در هیچ درایوری قابل Parameterized شدن نیستند.
    """
    if db_type == DbType.mysql:
        return f"`{name}`"
    if db_type == DbType.postgresql:
        return f'"{name}"'
    return f"[{name}]"  # mssql


def _connect(conn: SiteConnection):
    """اتصال خام به دیتابیس سایت بر اساس نوع آن (mssql/mysql/postgresql) با timeout ده ثانیه می‌سازد."""
    password = decrypt_secret(conn.password_encrypted)
    # درایور مناسب هر نوع دیتابیس
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
    یک Cursor می‌سازد که هر ردیف را به‌صورت دیکشنری برمی‌گرداند.
    MSSQL با as_dict، PostgreSQL با RealDictCursor؛ MySQL cursorclass را از قبل روی Connection دارد.
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
    ترددهای خام یک پرسنل را در حالت mapping_mode=single_column می‌خواند (همگام).
    ورودی: اتصال سایت، نگاشت، شماره‌ی پرسنل و بازه‌ی تاریخ شمسی فشرده.
    خروجی: [{"AttendanceDate": int, "AttendanceTime": int}, ...] مرتب بر اساس تاریخ و ساعت.
    نام جدول/ستون‌ها با _quote در متن Query قرار می‌گیرند و مقادیر Parameterized هستند؛
    نام‌های مستعار هم کوته می‌شوند تا PostgreSQL آن‌ها را کوچک نکند و کلید دیکشنری خروجی ثابت بماند.
    """
    q = lambda name: _quote(conn.db_type, name)  # noqa: E731
    connection = _connect(conn)
    try:
        # کوئری تردد در بازه‌ی ماه
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
    نشست‌های ورود/خروج یک پرسنل را در حالت mapping_mode=enter_exit_columns می‌خواند (همگام).
    هر ردیف یک نشست کامل با چهار ستون است؛ نشستی لحاظ می‌شود که تاریخ ورود یا خروجش داخل بازه‌ی ماه باشد.
    خروجی: [{"EnterDate": int, "EnterTime": int, "ExitDate": int|None, "ExitTime": int|None}, ...]؛ خروج NULL یعنی نشست باز است.
    """
    q = lambda name: _quote(conn.db_type, name)  # noqa: E731
    connection = _connect(conn)
    try:
        # کوئری نشست‌هایی که ورود یا خروجشان در بازه‌ی ماه است
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
    هر نشست (ورود+خروج) را به یک یا دو «تردد منفرد» تبدیل می‌کند: یکی برای ورود و
    اگر خروج ثبت شده باشد یکی هم برای خروج.
    خروجی هم‌شکل حالت single_column است ({"AttendanceDate", "AttendanceTime"}) تا ادامه‌ی خط لوله برای هر دو حالت یکی باشد.
    """
    transits: list[dict] = []
    # هر نشست به ترددهای جداگانه شکسته می‌شود
    for session in sessions:
        if session.get("EnterDate") is not None and session.get("EnterTime") is not None:
            transits.append({"AttendanceDate": session["EnterDate"], "AttendanceTime": session["EnterTime"]})
        if session.get("ExitDate") is not None and session.get("ExitTime") is not None:
            transits.append({"AttendanceDate": session["ExitDate"], "AttendanceTime": session["ExitTime"]})
    return transits


def _fetch_holidays_sync(
    conn: SiteConnection, mapping: AttendanceMapping, year: int, month: int, branch_value: str | None = None
) -> set[int]:
    """
    مجموعه‌ی شماره‌ی روزهای تعطیل یک ماه شمسی را از جدول تقویم سایت می‌خواند (همگام).
    جدول تقویم یک ردیف برای هر (سال، ماه) دارد با ستون‌های روز ۱ تا ۳۱؛ مقدار غیرصفر یعنی تعطیل.
    اگر نگاشت تقویم کامل تنظیم نشده باشد، مجموعه‌ی خالی برمی‌گردد (بدون خطا).
    """
    # نگاشت تقویم باید کامل باشد
    if not (
        mapping.calendar_table_name
        and mapping.calendar_year_column
        and mapping.calendar_month_column
        and mapping.calendar_day_column_prefix
    ):
        return set()

    q = lambda name: _quote(conn.db_type, name)  # noqa: E731
    day_columns_sql = ", ".join(q(f"{mapping.calendar_day_column_prefix}{i}") for i in range(1, 32))  # ستون‌های روز ۱..۳۱
    # تقویم ممکن است بین چند شعبه مشترک باشد؛ اگر ستون شعبه نگاشت شده، فقط ردیف شعبه‌ی همین سایت
    params = {"year": year, "month": month}
    branch_sql = ""
    branch_column = (getattr(mapping, "calendar_branch_column", None) or "").strip()
    if branch_column and branch_value:
        branch_sql = f"AND {q(branch_column)} = %(branch)s"
        params["branch"] = int(branch_value) if str(branch_value).isdigit() else branch_value  # کد عددی شعبه به int
    connection = _connect(conn)
    try:
        # ردیف تقویم این ماه
        query = f"""
            SELECT {day_columns_sql}
            FROM {q(mapping.calendar_table_name)}
            WHERE {q(mapping.calendar_year_column)} = %(year)s AND {q(mapping.calendar_month_column)} = %(month)s
            {branch_sql}
        """  # noqa: S608 - نام جدول/ستون فقط از تنظیمات Admin می‌آید
        with _dict_cursor(connection, conn.db_type) as cur:
            cur.execute(query, params)
            row = cur.fetchone()
    finally:
        connection.close()

    if row is None:
        return set()

    # هر ستون روز با مقدار غیرصفر، تعطیل است
    holidays = set()
    for i in range(1, 32):
        value = row.get(f"{mapping.calendar_day_column_prefix}{i}")
        if value is not None and value != 0:
            holidays.add(i)
    return holidays


# ---------- Cache کوتاه‌مدت و خواندن موازی ----------
# داشبورد و صفحه‌ی گزارش هر دو همین داده را می‌خواهند؛ جابه‌جایی بین آن‌ها در چند ثانیه
# نباید هر بار سه اتصال تازه به دیتابیس سایت باز کند. داده‌ی خام هر (اتصال، نگاشت،
# پرسنل، بازه، شعبه) برای مدت کوتاهی در حافظه‌ی همین worker می‌ماند.
_CACHE_TTL_SECONDS = 30
_CACHE_MAX_ENTRIES = 500
_cache: dict[tuple, tuple[float, tuple]] = {}


def _cache_get(key: tuple):
    """مقدار Cache شده را اگر منقضی نشده باشد برمی‌گرداند، وگرنه None."""
    item = _cache.get(key)
    if item is None:
        return None
    stored_at, value = item
    if time.monotonic() - stored_at > _CACHE_TTL_SECONDS:
        _cache.pop(key, None)
        return None
    return value


def _cache_put(key: tuple, value: tuple) -> None:
    """مقدار را ذخیره می‌کند؛ اگر Cache پر شد، موارد منقضی و در صورت نیاز قدیمی‌ترین‌ها حذف می‌شوند."""
    now = time.monotonic()
    if len(_cache) >= _CACHE_MAX_ENTRIES:
        for k in [k for k, (t, _v) in _cache.items() if now - t > _CACHE_TTL_SECONDS]:
            _cache.pop(k, None)
        while len(_cache) >= _CACHE_MAX_ENTRIES:
            _cache.pop(next(iter(_cache)))
    _cache[key] = (now, value)


async def _fetch_month_sources(
    site_connection, mapping, emp_no, from_date, to_date, year, month, branch_value, branch_int, kara_names
):
    """
    سه منبع مستقل گزارش را هم‌زمان (هر کدام در thread جدا) می‌خواند:
    ترددهای خام، تعطیلات تقویمی و لایه‌ی کاراوب. قبلاً پشت سر هم اجرا می‌شدند.
    خروجی: (raw_rows, holidays, overlay). خطای تردد خام به MonthlyAttendanceError تبدیل
    می‌شود؛ شکست دو لایه‌ی اختیاری فقط لاگ می‌شود.
    """

    async def _raw():
        # حالت نشستی به تردد منفرد نرمال می‌شود
        if mapping.mapping_mode == AttendanceMappingMode.enter_exit_columns:
            sessions = await asyncio.to_thread(
                _fetch_raw_rows_enter_exit_sync, site_connection, mapping, emp_no, from_date, to_date
            )
            return _normalize_enter_exit_sessions(sessions)
        return await asyncio.to_thread(
            _fetch_raw_rows_single_column_sync, site_connection, mapping, emp_no, from_date, to_date
        )

    async def _holidays():
        return await asyncio.to_thread(_fetch_holidays_sync, site_connection, mapping, year, month, branch_value)

    async def _overlay():
        if kara_names is None:
            return None
        return await asyncio.to_thread(
            kara_attendance_overlay.fetch_overlay_sync,
            site_connection,
            kara_names,
            emp_no,
            from_date,
            to_date,
            branch_int,
        )

    raw_res, hol_res, ov_res = await asyncio.gather(_raw(), _holidays(), _overlay(), return_exceptions=True)

    if isinstance(raw_res, MonthlyAttendanceError):
        raise raw_res
    if isinstance(raw_res, BaseException):
        logger.error("خطا در دریافت گزارش تردد ماهانه (Emp_No=%s)", emp_no, exc_info=raw_res)
        raise MonthlyAttendanceError("اتصال به سیستم تردد با خطا مواجه شد — لطفاً بعداً دوباره تلاش کنید") from raw_res

    # تعطیلات تقویمی (اختیاری): شکست آن گزارش اصلی را خراب نمی‌کند
    if isinstance(hol_res, BaseException):
        logger.error("خطا در دریافت تقویم/تعطیلات ماهانه (سایت=%s)", site_connection.site_id, exc_info=hol_res)
        hol_res = set()
    # لایه‌ی مرخصی/ماموریت/تقویم کاری (فقط کاراوب روی SQL Server)؛ شکست آن گزارش اصلی را خراب نمی‌کند
    if isinstance(ov_res, BaseException):
        logger.error("خطا در دریافت مرخصی/ماموریت برای گزارش تردد (Emp_No=%s)", emp_no, exc_info=ov_res)
        ov_res = None
    return raw_res, hol_res, ov_res


async def get_monthly_attendance(
    site_connection: SiteConnection,
    mapping: AttendanceMapping,
    *,
    personnel_code: str,
    year: int,
    month: int,
    kara_names=None,
    type_titles: dict[int, str] | None = None,
    branch_value: str | None = None,
) -> dict:
    """
    گزارش تردد ماهانه‌ی یک پرسنل را می‌سازد.
    ورودی: اتصال و نگاشت سایت، کد پرسنلی (عددی)، سال/ماه شمسی، نام‌های کاراوب (اختیاری)،
    عنوان انواع مرخصی پرتال (card_no -> عنوان) و کد شعبه.
    خروجی: {"year", "month", "max_transits_in_month", "days": [...]} با یک آیتم برای هر روز ماه
    (روزهای بدون رکورد با transits خالی)؛ هر روز شامل ترددها، وضعیت روز، علامت‌های ساعتی و روزانه است.
    خطای اتصال/کوئری تردد به MonthlyAttendanceError تبدیل می‌شود؛ شکست لایه‌های اختیاری فقط لاگ می‌شود.
    """
    # کد پرسنلی در دستگاه‌ها عددی است
    try:
        emp_no = int(personnel_code)
    except (TypeError, ValueError):
        raise MonthlyAttendanceError("کد پرسنلی این کاربر عددی نیست — با فرمت مورد انتظار این گزارش سازگار نیست")

    from_date, to_date = jalali_year_month_to_yyyymmdd_range(year, month)  # اولین و آخرین روز ماه (YYYYMMDD)

    branch_int = int(branch_value) if branch_value is not None and str(branch_value).isdigit() else None  # کد شعبه به int
    use_overlay = kara_names is not None and site_connection.db_type == DbType.mssql
    cache_key = (
        site_connection.id,
        mapping.id,
        emp_no,
        from_date,
        to_date,
        branch_value,
        use_overlay,
    )
    cached = _cache_get(cache_key)
    if cached is not None:
        raw_rows, holidays, overlay = cached
    else:
        raw_rows, holidays, overlay = await _fetch_month_sources(
            site_connection, mapping, emp_no, from_date, to_date, year, month, branch_value, branch_int,
            kara_names if use_overlay else None,
        )
        _cache_put(cache_key, (raw_rows, holidays, overlay))

    def _label(card_no: int) -> dict:
        """برای یک شماره کارت، {"code", "label", "kind"} می‌سازد؛ عنوان پرتال بر عنوان کاراوب مقدم است."""
        card = (overlay or {}).get("cards", {}).get(card_no, {})
        # اولویت عنوان: نوع درخواست تعریف‌شده در پرتال، سپس عنوان کارت در کاراوب، سپس «کد N»
        title = (type_titles or {}).get(card_no) or card.get("title") or f"کد {card_no}"
        return {"code": card_no, "label": title, "kind": card.get("kind", kara_attendance_overlay.KIND_OTHER)}

    # گروه‌بندی ترددها بر اساس همان ستون Date خام دستگاه
    rows_by_date: dict[int, list[dict]] = {}
    for row in raw_rows:
        rows_by_date.setdefault(row["AttendanceDate"], []).append(row)

    def _mark(card_no: int, start: int | None, end: int | None) -> dict:
        """علامت ساعتی: برچسب کارت به‌همراه from/to (HH:MM، ساعت روز بعد به همان روز نگاشت می‌شود) و مدت به دقیقه."""
        mark = _label(card_no)
        mark["from"] = _format_time(start % 2400) if start is not None else None
        mark["to"] = _format_time(end % 2400) if end is not None else None
        mark["minutes"] = _minutes_between(start, end)
        return mark

    def _mark_once(seen: dict, card_no: int, start: int | None, end: int | None) -> dict:
        """
        علامت ساعتی برای یک بازه می‌سازد و بازه‌ی تکراری را دوباره نمی‌سازد.
        اگر هم روی خروج و هم روی ورودِ برگشت کارت زده شود، هر دو به همان بازه اشاره می‌کنند و
        مثل کاراوب فقط یک‌بار حساب می‌شود. علامت تازه‌ساخته با کلید موقت "_new" مشخص می‌شود.
        """
        key = (start, end)
        if key in seen:
            return seen[key]
        mark = _mark(card_no, start, end)
        mark["_new"] = True
        seen[key] = mark
        return mark

    # علامت‌های ساعتی بر اساس شیفت‌بندی کارکرد روزانه‌ی کاراوب:
    # ترتیب ورود/خروج از کارکرد روزانه خوانده می‌شود تا شیفت شب (خروج بعد از نیمه‌شب با
    # تاریخ روز بعد) هم درست محاسبه شود؛ علامت کارت (Status) از خودِ جدول تردد (زنده) می‌آید
    seen_by_shift: dict[int, dict] = {}  # روز شیفت -> بازه‌های دیده‌شده
    shift_punch_marks: dict[tuple[int, int], dict | None] = {}  # (تاریخ واقعی، ساعت) -> علامت یا None
    shift_hourly: dict[int, list[dict]] = {}  # روز شیفت -> لیست علامت‌های ساعتی یکتا
    for shift_date, info in ((overlay or {}).get("shift_days") or {}).items():
        times = info["cards"]
        for index, kara_time in enumerate(times):
            # ساعت >= ۲۴۰۰ یعنی تردد در تاریخ روز بعد ثبت شده
            actual_date = shift_date if kara_time < 2400 else kara_attendance_overlay.next_jalali_date(shift_date)
            actual_time = kara_time % 2400
            status_code = overlay["punch_status"].get((actual_date, actual_time))
            mark = None
            if status_code:
                start, end = kara_attendance_overlay.hourly_interval(times, index, info["bounds"])
                mark = _mark_once(seen_by_shift.setdefault(shift_date, {}), status_code, start, end)
                if mark.pop("_new", False):
                    shift_hourly.setdefault(shift_date, []).append(mark)
            shift_punch_marks[(actual_date, actual_time)] = mark

    today_int = _today_jalali_int()
    days_in_month = to_date % 100  # عدد روزِ to_date، چون to_date آخرین روز واقعی ماه است
    max_transits = 0
    days_out = []

    # ساخت خروجی روزبه‌روز برای همه‌ی روزهای ماه
    for day in range(1, days_in_month + 1):
        date_int = year * 10000 + month * 100 + day
        day_rows = rows_by_date.get(date_int, [])
        transits = [_format_time(r["AttendanceTime"]) for r in day_rows]
        max_transits = max(max_transits, len(transits))

        # علامت مرخصی/ماموریت ساعتی روی هر تردد (مثل محاسبه‌ی کاراوب، ستون S_Sha):
        # تردد ورود = از خروج قبلی یا شروع شیفت تا همین تردد؛ تردد خروج = از همین تردد تا ورود بعدی یا پایان شیفت
        transit_marks: list[dict | None] = []
        hourly: list[dict] = []
        daily_mark = None
        if overlay is not None:
            covered = all((date_int, t) in shift_punch_marks for t in (r["AttendanceTime"] for r in day_rows))  # همه‌ی ترددهای روز در کارکرد روزانه هستند؟
            if covered:
                # ترددهای این روز در کارکرد روزانه‌ی کاراوب شیفت‌بندی شده‌اند؛ علامت‌های آماده استفاده می‌شوند
                for r in day_rows:
                    mark = shift_punch_marks[(date_int, r["AttendanceTime"])]
                    transit_marks.append(mark)
                hourly.extend(shift_hourly.get(date_int, []))
            else:
                # هنوز در کارکرد روزانه محاسبه نشده؛ همان قاعده روی ترددهای خام همین تاریخ اعمال می‌شود
                shift = (overlay.get("shift_times") or {}).get(date_int)
                times = [r["AttendanceTime"] for r in day_rows]
                seen_raw: dict = {}
                for index, r in enumerate(day_rows):
                    status_code = overlay["punch_status"].get((date_int, r["AttendanceTime"]))
                    if not status_code:
                        transit_marks.append(None)
                        continue
                    start, end = kara_attendance_overlay.hourly_interval(times, index, shift)
                    mark = _mark_once(seen_raw, status_code, start, end)
                    transit_marks.append(mark)
                    if mark.pop("_new", False):
                        hourly.append(mark)
            # مرخصی/ماموریت روزانه (در روز تعطیل نمایش داده نمی‌شود)
            daily_code = overlay["daily"].get(date_int)
            if daily_code and day not in holidays:
                daily_mark = _label(daily_code)

        # وضعیت روز:
        #   holiday = تعطیل تقویمی یا روز غیرکاری شیفت خودِ فرد (کارکرد روزانه)
        #   leave/mission/other = نوع مرخصی/ماموریت روزانه
        #   absent  = روز کاری گذشته، بدون هیچ تردد و بدون مرخصی/ماموریت روزانه (امروز و آینده هرگز غیبت نمی‌گیرند)
        is_off = day in holidays or bool(overlay and overlay.get("work_calendar", {}).get(date_int))
        if is_off:
            day_status = "holiday"
        elif daily_mark is not None:
            day_status = daily_mark["kind"]
        elif overlay is not None and overlay.get("daily_enabled") and not transits and date_int < today_int:
            day_status = "absent"
        else:
            day_status = None

        # آیتم خروجی این روز
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
