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
    ۹ ماموریت). بازه از همان تردد تا تردد بعدی همان روز است. این علامت یا
    از خودِ دستگاه (کارت مرخصی/ماموریت) می‌آید یا از تأیید درخواست.

نام همه جدول/ستون‌ها از تنظیمات سایت می‌آید (app/services/kara_schema.py).

همه چیز فقط خواندنی است و اگر هر بخش شکست بخورد، گزارش اصلی تردد
بدون این لایه نمایش داده می‌شود (مثل تقویم تعطیلات).
"""
from __future__ import annotations

import re

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
    D = lambda role: n.c("datafile", role)  # noqa: E731
    M = lambda role: n.c("mor_mam", role)  # noqa: E731
    connection = _connect(conn)
    try:
        with connection.cursor(as_dict=True) as cur:
            cur.execute(
                f"SELECT {D('date')} AS DateInt, {D('time')} AS TimeInt, {D('status')} AS Status "
                f"FROM {n.t('datafile')} WHERE {D('emp_no')} = %(e)s AND {D('date')} BETWEEN %(f)s AND %(t)s "
                f"AND {D('status')} <> 0",
                {"e": emp_no, "f": from_date, "t": to_date},
            )
            punch_status = {(r["DateInt"], r["TimeInt"]): int(r["Status"]) for r in cur.fetchall()}

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
            W = lambda role: n.c("daily_work", role)  # noqa: E731
            cur.execute(
                f"SELECT w.{W('date')} AS DateInt, CASE WHEN s.{n.c('shifts', 'shift_no')} IS NULL THEN 1 ELSE 0 END AS IsOff "
                f"FROM {n.t('daily_work')} w LEFT JOIN {n.t('shifts')} s "
                f"ON s.{n.c('shifts', 'shift_no')} = w.{W('shift_no')} "
                f"WHERE w.{W('emp_no')} = %(e)s AND w.{W('date')} BETWEEN %(f)s AND %(t)s",
                {"e": emp_no, "f": from_date, "t": to_date},
            )
            work_calendar = {int(r["DateInt"]): bool(r["IsOff"]) for r in cur.fetchall()}

            card_nos = set(punch_status.values()) | {int(r["CardNo"]) for r in daily_rows}
            cards: dict[int, dict] = {}
            if card_nos:
                placeholders = ", ".join(f"%(c{i})s" for i in range(len(card_nos)))
                params = {f"c{i}": c for i, c in enumerate(sorted(card_nos))}
                cur.execute(
                    f"SELECT {n.cards_no} AS CardNo, {n.cards_title} AS Title, {n.c('cards', 'card_type')} AS CardType "
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

    return {"punch_status": punch_status, "daily": daily, "cards": cards, "work_calendar": work_calendar}
