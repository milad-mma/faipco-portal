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

همه چیز فقط خواندنی است و اگر هر بخش شکست بخورد، گزارش اصلی تردد
بدون این لایه نمایش داده می‌شود (مثل تقویم تعطیلات).
"""
from __future__ import annotations

import re

import pymssql

from app.core.security import decrypt_secret
from app.models.site import SiteConnection

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


def fetch_overlay_sync(conn: SiteConnection, emp_no: int, from_date: int, to_date: int) -> dict:
    """
    خروجی:
      {
        "punch_status": {(date, time): status, ...}   # فقط Status غیرصفر
        "daily": {date: card_no, ...}                 # روزهای مرخصی/ماموریت روزانه
        "cards": {card_no: {"title": str, "kind": str}, ...}
      }
    """
    connection = _connect(conn)
    try:
        with connection.cursor(as_dict=True) as cur:
            cur.execute(
                "SELECT [Date], [Time], [Status] FROM [DataFile] "
                "WHERE [Emp_No] = %(e)s AND [Date] BETWEEN %(f)s AND %(t)s AND [Status] <> 0",
                {"e": emp_no, "f": from_date, "t": to_date},
            )
            punch_status = {(r["Date"], r["Time"]): int(r["Status"]) for r in cur.fetchall()}

            cur.execute(
                "SELECT m.[Type], m.[S_Date], ISNULL(m.[E_Date], m.[S_Date]) AS EDate "
                "FROM [Mor_Mam] m JOIN [Cards] c ON c.[Card_No] = m.[Type] "
                "WHERE m.[Emp_No] = %(e)s AND c.[IsDay] = 1 AND (m.[Inc_Type] = 0 OR m.[Inc_Type] IS NULL) "
                "AND m.[S_Date] <= %(t)s AND ISNULL(m.[E_Date], m.[S_Date]) >= %(f)s "
                "ORDER BY m.[RefNumber]",
                {"e": emp_no, "f": from_date, "t": to_date},
            )
            daily_rows = list(cur.fetchall())

            card_nos = set(punch_status.values()) | {int(r["Type"]) for r in daily_rows}
            cards: dict[int, dict] = {}
            if card_nos:
                placeholders = ", ".join(f"%(c{i})s" for i in range(len(card_nos)))
                params = {f"c{i}": c for i, c in enumerate(sorted(card_nos))}
                cur.execute(
                    f"SELECT [Card_No], [DefaultTitle], [CardType] FROM [Cards] WHERE [Card_No] IN ({placeholders})",
                    params,
                )
                for r in cur.fetchall():
                    cards[int(r["Card_No"])] = {
                        "title": _clean_title(r.get("DefaultTitle")),
                        "kind": _kind_for_card_type(r.get("CardType")),
                    }
    finally:
        connection.close()

    daily: dict[int, int] = {}
    for r in daily_rows:
        start, end = int(r["S_Date"]), int(r["EDate"])
        # بازه‌های تاریخ شمسی فشرده هستند (YYYYMMDD) - روز به روز داخل همان ماه گزارش
        for date_int in range(max(start, from_date), min(end, to_date) + 1):
            if 1 <= date_int % 100 <= 31 and 1 <= (date_int // 100) % 100 <= 12:
                daily[date_int] = int(r["Type"])

    return {"punch_status": punch_status, "daily": daily, "cards": cards}
