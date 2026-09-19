"""
لایه «مرخصی/ماموریت» روی گزارش تردد ماهانه - فقط برای سایت‌های کاراوب.

کاراوب مرخصی/ماموریت را در دو جای مختلف ثبت می‌کند (با داده واقعی بررسی شد):

روزانه (مرخصی استحقاقی، استعلاجی، ماموریت روزانه، ...):
    یک ردیف در Mor_Mam با بازه S_Date..E_Date و Type = شماره کارت.
    فقط ردیف‌های «مصرف» (Inc_Type = 0 برای مرخصی استحقاقی، NULL برای بقیه)
    و فقط کارت‌های روزانه (Cards.IsDay = 1) - ردیف‌های افزایش خودکار ماهانه
    (Inc_Type=6) و کسر ساعتی ماهانه (Inc_Type=2) کنار گذاشته می‌شوند.

ساعتی (مرخصی ساعتی، ماموریت ساعتی):
    روی خودِ تردد: DataFile.Status = شماره کارت (مثلاً ۱۷ مرخصی شخصی،
    ۹ ماموریت). این علامت یا از خودِ دستگاه (کارت مرخصی/ماموریت) می‌آید یا
    از تأیید درخواست. بازه آن به «ورود» یا «خروج» بودن تردد بستگی دارد
    (تأییدشده با کارکرد روزانه کاراوب - ستون S_Sha، ۱۴۰۵/۰۶/۲۸):
      - تردد ورود (اول، سوم، ... روز): از خروج قبلی - یا شروع شیفت اگر اولین
        تردد است - تا همین تردد. مثال: ورود ۰۸:۱۳ با کارت مرخصی، شیفت ۰۶:۳۰
        -> مرخصی ۰۶:۳۰ تا ۰۸:۱۳ (۱:۴۳)
      - تردد خروج (دوم، چهارم، ...): از همین تردد تا ورود بعدی - یا پایان
        شیفت اگر ورودی بعدش نیست. مثال: خروج ۰۸:۵۲ و ورود ۱۰:۳۱ -> ۱:۳۹

نام همه جدول/ستون‌ها از تنظیمات سایت می‌آید (app/services/kara_schema.py).

همه چیز فقط خواندنی است و اگر هر بخش شکست بخورد، گزارش اصلی تردد
بدون این لایه نمایش داده می‌شود (مثل تقویم تعطیلات).
"""
from __future__ import annotations

import re

import jdatetime
import pymssql

from app.core.security import decrypt_secret
from app.models.site import SiteConnection
from app.services.kara_schema import KaraNames

KIND_LEAVE = "leave"
KIND_MISSION = "mission"
KIND_OTHER = "other"


def _connect(conn: SiteConnection):
    return pymssql.connect(
        server=conn.host,
        port=str(conn.port),
        database=conn.database_name,
        user=conn.username,
        password=decrypt_secret(conn.password_encrypted),
        timeout=10,
        login_timeout=10,
    )


def _clean_title(title: str | None) -> str:
    # «ماموریت اداری ساعتی1» / «مرخصی روزانه بدون حقوق 3» -> بدون شماره انتهایی
    cleaned = re.sub(r"\s+", " ", title or "").strip()
    return re.sub(r"\s*[0-9۰-۹]+$", "", cleaned).strip()


def _is_thursday(date_int: int) -> bool:
    j = jdatetime.date(date_int // 10000, (date_int // 100) % 100, date_int % 100)
    return j.togregorian().weekday() == 3


def _kind_for_card_type(card_type) -> str:
    # Cards.CardType در داده واقعی: ۳ = ماموریت، ۵/۷ = مرخصی (با/بدون حقوق)،
    # ۲ = تاخیر/تعجیل و مانند آن
    if card_type == 3:
        return KIND_MISSION
    if card_type in (5, 7):
        return KIND_LEAVE
    return KIND_OTHER


def fetch_overlay_sync(conn: SiteConnection, n: KaraNames, emp_no: int, from_date: int, to_date: int) -> dict:
    """
    خروجی:
      {
        "punch_status": {(date, time): status, ...}   # فقط Status غیرصفر
        "daily": {date: card_no, ...}                 # روزهای مرخصی/ماموریت روزانه
        "cards": {card_no: {"title": str, "kind": str}, ...}
        "work_calendar": {date: is_off_day, ...}      # فقط روزهایی که کارکرد روزانه دارند
      }
    همه نام جدول/ستون‌ها از تنظیمات سایت (KaraNames) می‌آیند.
    """
    M = lambda role: n.c("mor_mam", role)  # noqa: E731
    punch_status: dict = {}
    daily_rows: list = []
    work_calendar: dict[int, bool] = {}
    shift_times: dict[int, tuple[int, int]] = {}
    cards: dict[int, dict] = {}
    connection = _connect(conn)
    try:
        with connection.cursor(as_dict=True) as cur:
            # ساعتی: علامت روی خودِ تردد (جدول تردد از تب «نگاشت تردد»)
            if n.can_read_hourly_marks:
                status_col = n.c("datafile", "status")
                cur.execute(
                    f"SELECT {n.df_date} AS DateInt, {n.df_time} AS TimeInt, {status_col} AS Status "
                    f"FROM {n.df_table} WHERE {n.df_emp_no} = %(e)s AND {n.df_date} BETWEEN %(f)s AND %(t)s "
                    f"AND {status_col} <> 0",
                    {"e": emp_no, "f": from_date, "t": to_date},
                )
                punch_status = {(r["DateInt"], r["TimeInt"]): int(r["Status"]) for r in cur.fetchall()}

            # روزانه: جدول مرخصی/ماموریت روزانه (فقط کارت‌های روزانه و ردیف‌های مصرف)
            if n.can_read_daily_marks:
                cur.execute(
                    f"SELECT m.{M('type')} AS CardNo, m.{M('s_date')} AS SDate, "
                    f"ISNULL(m.{M('e_date')}, m.{M('s_date')}) AS EDate "
                    f"FROM {n.t('mor_mam')} m JOIN {n.cards_table} c ON c.{n.cards_no} = m.{M('type')} "
                    f"WHERE m.{M('emp_no')} = %(e)s AND c.{n.c('cards', 'is_day')} = 1 "
                    f"AND (m.{M('inc_type')} = 0 OR m.{M('inc_type')} IS NULL) "
                    f"AND m.{M('s_date')} <= %(t)s AND ISNULL(m.{M('e_date')}, m.{M('s_date')}) >= %(f)s "
                    f"ORDER BY m.{M('ref_number')}",
                    {"e": emp_no, "f": from_date, "t": to_date},
                )
                daily_rows = list(cur.fetchall())

            # روزهای غیرکاریِ خودِ این پرسنل (مثلاً جمعه یا روز استراحت شیفتی):
            # شیفت آن روز در کارکرد روزانه، در جدول شیفت‌ها تعریف نشده (مثل ۵۰۱)
            if n.can_read_work_calendar:
                W = lambda role: n.c("daily_work", role)  # noqa: E731
                sh_no = n.c("shifts", "shift_no")
                with_times = all(n.has("shifts", r) for r in ("start_time", "start_time5", "end_time", "end_time5"))
                times_sql = (
                    f", s.{n.c('shifts', 'start_time')} AS StartTime, s.{n.c('shifts', 'start_time5')} AS StartTime5, "
                    f"s.{n.c('shifts', 'end_time')} AS EndTime, s.{n.c('shifts', 'end_time5')} AS EndTime5"
                    if with_times
                    else ""
                )
                cur.execute(
                    f"SELECT w.{W('date')} AS DateInt, CASE WHEN s.{sh_no} IS NULL THEN 1 ELSE 0 END AS IsOff{times_sql} "
                    f"FROM {n.t('daily_work')} w LEFT JOIN {n.t('shifts')} s ON s.{sh_no} = w.{W('shift_no')} "
                    f"WHERE w.{W('emp_no')} = %(e)s AND w.{W('date')} BETWEEN %(f)s AND %(t)s",
                    {"e": emp_no, "f": from_date, "t": to_date},
                )
                for r in cur.fetchall():
                    date_int = int(r["DateInt"])
                    work_calendar[date_int] = bool(r["IsOff"])
                    if with_times and not r["IsOff"]:
                        thursday = _is_thursday(date_int)
                        start = r["StartTime5"] if thursday else r["StartTime"]
                        end = r["EndTime5"] if thursday else r["EndTime"]
                        if start is not None and end is not None:
                            shift_times[date_int] = (int(start), int(end))

            card_nos = set(punch_status.values()) | {int(r["CardNo"]) for r in daily_rows}
            if card_nos and n.has_cards and getattr(n.leave, "card_lookup_desc_column", None):
                placeholders = ", ".join(f"%(c{i})s" for i in range(len(card_nos)))
                params = {f"c{i}": c for i, c in enumerate(sorted(card_nos))}
                card_type_sql = (
                    f"{n.c('cards', 'card_type')} AS CardType" if n.has("cards", "card_type") else "NULL AS CardType"
                )
                cur.execute(
                    f"SELECT {n.cards_no} AS CardNo, {n.cards_title} AS Title, {card_type_sql} "
                    f"FROM {n.cards_table} WHERE {n.cards_no} IN ({placeholders})",
                    params,
                )
                for r in cur.fetchall():
                    cards[int(r["CardNo"])] = {
                        "title": _clean_title(r.get("Title")),
                        "kind": _kind_for_card_type(r.get("CardType")),
                    }
    finally:
        connection.close()

    daily: dict[int, int] = {}
    for r in daily_rows:
        start, end = int(r["SDate"]), int(r["EDate"])
        # بازه‌های تاریخ شمسی فشرده هستند (YYYYMMDD) - روز به روز داخل همان ماه گزارش
        for date_int in range(max(start, from_date), min(end, to_date) + 1):
            if 1 <= date_int % 100 <= 31 and 1 <= (date_int // 100) % 100 <= 12:
                daily[date_int] = int(r["CardNo"])

    return {
        "punch_status": punch_status,
        "daily": daily,
        "cards": cards,
        "work_calendar": work_calendar,
        "shift_times": shift_times,
        # «غیبت» فقط وقتی قابل‌تشخیص است که مرخصی/ماموریت روزانه خوانده شده باشد
        "daily_enabled": n.can_read_daily_marks,
    }


def is_enabled(n: KaraNames) -> bool:
    """آیا حداقل یکی از بخش‌های این لایه نگاشت شده است؟"""
    return n.can_read_hourly_marks or n.can_read_daily_marks or n.can_read_work_calendar
