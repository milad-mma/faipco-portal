"""
نوشتن اثر درخواست‌های مرخصی/ماموریت/تردد فراموش‌شده در دیتابیس کاراوب (SQL Server).

این ماژول همان تغییراتی را در جدول‌های کاراوب انجام می‌دهد که خودِ برنامه‌ی
کاراوب هنگام ثبت، تأیید نهایی، لغو و ارجاع یک درخواست انجام می‌دهد، تا
گزارش‌ها و کارکرد کاراوب با درخواست‌های ثبت‌شده در پرتال هم‌خوان بمانند.

ثبت درخواست (ستون‌های اضافه‌ی WF_Requests):
    SubmittedByEmployeeID = کد پرسنلی درخواست‌دهنده
    Requested_Time       = همان Duration (رشته)
    DutyTools / DutyTamin = '' (نه NULL)
    CurSection           = Sec_No واحدِ تأییدکننده

تأیید نهایی - درخواست ساعتی (StartHour دارد):
    اولین تردد همان روز که ساعتش بین StartHour و EndHour است پیدا می‌شود:
      - اگر بود: DataFile.Status = Card_No، Duration = مدت درخواست،
        ApplicationId = (4 << 16) | منبع اولیه تردد؛ یک ردیف LogDataFile؛
        AcceptCode = 0 (اعمال‌شده)
      - اگر نبود: فقط AcceptCode = 8 (تأییدشده، اعمال‌نشده) - هیچ جدول
        دیگری تغییر نمی‌کند و پرتال هشداری نمایش نمی‌دهد.

تأیید نهایی - درخواست روزانه:
    یک ردیف Mor_Mam + یک ردیف LogMorMam (ChangeType=1)، AcceptCode = 0.
    فقط مرخصی استحقاقی (کارت ۵۷) از مانده کسر می‌شود: Inc_Type=0 و
    Requested = منفیِ مجموع ساعت کسر هر روز از شیفت همان روز (Shifts.
    Kasr_Gh، پنجشنبه Kasr_Gh5، روز غیرکاری ۰) به فرمت HHMM؛
    StandardRequested همان به دقیقه. بقیه انواع روزانه (ماموریت ۵۱،
    استعلاجی ۶۰، ...) Requested = تعداد روز تقویمی و Inc_Type = NULL.

لغو اثر (رد/حذف/تغییر مدیریتی یک درخواستِ قبلاً تأییدشده):
    ساعتی: Status تردد اعمال‌شده به ۰ برمی‌گردد + LogDataFile
    روزانه: ردیف Mor_Mam حذف + LogMorMam (ChangeType=3)

Checksum: الگوریتم محاسبه‌ی آن در دسترس نیست؛ ۰ نوشته می‌شود (بسیاری از
ردیف‌های موجود Mor_Mam/DataFile هم ۰ دارند و کاراوب با آن‌ها مشکلی ندارد).

فقط برای SQL Server (کاراوب). همه‌ی توابع یک cursor از pymssql (as_dict=True)
و یک KaraNames (نام جدول/ستون‌ها از تنظیمات سایت) می‌گیرند و commit را به
فراخوان می‌سپارند تا هر عملیات در یک تراکنش انجام شود. هیچ نام جدول/ستونی
در این فایل مستقیم نوشته نشده (app/services/kara_schema.py).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import jdatetime

from app.services.kara_schema import KaraNames, quote_mssql

_KARA_TZ = ZoneInfo("Asia/Tehran")  # کاراوب همه‌ی تاریخ/ساعت‌ها را به وقت ایران می‌نویسد


def kara_now() -> datetime:
    """
    زمان فعلی به وقت ایران بدون tzinfo برمی‌گرداند.
    سرور پرتال UTC است و datetime.now() خام ۳:۳۰ ساعت عقب‌تر از ساعتی می‌شد که کاراوب انتظار دارد.
    """
    return datetime.now(_KARA_TZ).replace(tzinfo=None)

# مقادیر AcceptCode درخواست در کاراوب
ACCEPT_APPLIED = 0  # تأیید و اعمال‌شده
ACCEPT_APPROVED_NOT_APPLIED = 8  # تأییدشده ولی روی ترددی اعمال نشده
ACCEPT_CANCELLED = 22
MISSION_OPERATION_ID = 3  # OperationsID مأموریت (WF_OperationTypes)؛ مرخصی ۵

# کارت‌هایی که از مانده‌ی مرخصی (ساعتی) کسر می‌شوند (مرخصی استحقاقی)
ENTITLEMENT_CARDS = {57}

# پرچم «ویرایش‌شده توسط برنامه X» روی ApplicationId تردد = شناسه‌ی برنامه << 16
# (۶۵۵۳۶ = دسکتاپ کاراوب، ۲۶۲۱۴۴ = وب کاراوب)
_EDITOR_SHIFT = 16

_THURSDAY = 3  # date.weekday()
_FRIDAY = 4


# ---------- کمکی‌ها ----------


def _jalali_int(d: date) -> int:
    """تاریخ میلادی را به عدد فشرده‌ی شمسی YYYYMMDD تبدیل می‌کند."""
    j = jdatetime.date.fromgregorian(date=d)
    return j.year * 10000 + j.month * 100 + j.day


def _now_parts() -> tuple[datetime, int, int]:
    """(datetime فعلی به وقت ایران، تاریخ شمسی فشرده‌ی امروز، ساعت فعلی به فرمت HHMM) را برمی‌گرداند."""
    now = kara_now()
    return now, _jalali_int(now.date()), now.hour * 100 + now.minute


def _to_date(value) -> date | None:
    """مقدار datetime یا date را به date تبدیل می‌کند؛ None بدون تغییر."""
    if value is None:
        return None
    return value.date() if hasattr(value, "date") else value


def _hhmm_to_minutes(value: int) -> int:
    """ساعت فشرده‌ی HHMM را به دقیقه تبدیل می‌کند (None/خالی = ۰)."""
    value = int(value or 0)
    return (value // 100) * 60 + value % 100


def _minutes_to_hhmm(minutes: int) -> int:
    """دقیقه را به ساعت فشرده‌ی HHMM تبدیل می‌کند."""
    return (minutes // 60) * 100 + minutes % 60


def get_sec_no(cur, n: KaraNames, emp_no: int | None) -> int | None:
    """شماره‌ی واحد (Sec_No) یک پرسنل را از جدول پرسنل کاراوب می‌خواند؛ None اگر نگاشت نشده یا پیدا نشود."""
    if emp_no is None or not n.has_employee_section:
        return None
    cur.execute(
        f"SELECT TOP 1 {n.employee_sec_no} AS SecNo FROM {n.employee_table} WHERE {n.employee_emp_no} = %(e)s",
        {"e": emp_no},
    )
    row = cur.fetchone()
    return row["SecNo"] if row else None


def _resolve_kara_user(cur, n: KaraNames, emp_nos: list[int | None]) -> tuple[str, str]:
    """
    (UserId, Username) کاربر کاراوبی را برمی‌گرداند که تغییر به نامش ثبت می‌شود.
    ورودی: لیست کد پرسنلی به ترتیب اولویت (مدیر تأییدکننده، درخواست‌دهنده، ...)؛
    اولین نفری که کاربر کاراوب دارد انتخاب می‌شود، وگرنه قدیمی‌ترین کاربر فعال (ستون‌ها NOT NULL هستند).
    """
    select = (
        f"SELECT TOP 1 {n.c('users', 'user_id')} AS UserId, {n.c('users', 'username')} AS Username "
        f"FROM {n.t('users')} "
    )
    # کاربر هر پرسنل به ترتیب اولویت؛ کاربر فعال و قدیمی‌تر مقدم است
    for emp_no in emp_nos:
        if emp_no is None:
            continue
        cur.execute(
            select + f"WHERE {n.c('users', 'emp_no')} = %(e)s "
            f"ORDER BY {n.c('users', 'is_active')} DESC, {n.c('users', 'creation_date')}",
            {"e": emp_no},
        )
        row = cur.fetchone()
        if row:
            return str(row["UserId"]), row["Username"]
    # هیچ‌کدام کاربر نداشتند: قدیمی‌ترین کاربر فعال
    cur.execute(select + f"WHERE {n.c('users', 'is_active')} = 1 ORDER BY {n.c('users', 'creation_date')}")
    row = cur.fetchone()
    if not row:
        raise RuntimeError("هیچ کاربر فعالی در جدول کاربران کاراوب پیدا نشد")
    return str(row["UserId"]), row["Username"]


def _log_user(cur, n: KaraNames, requester_emp_no: int, others: list[int | None]) -> tuple[str, str]:
    """
    کاربر ردیف‌های لاگ (LogDataFile / LogMorMam) تغییراتی که پرتال برای یک درخواست می‌نویسد، مثل کاراوب: حساب کاراوبِ
    خودِ درخواست‌دهنده (۱۷۱ → Eskandarlou = ۲۳۵۵۰۸، ۱۸۳ → it = ۲۲۵۷۳۵). اگر درخواست‌دهنده حساب کاراوب ندارد، Username
    کد پرسنلی اوست و UserId (اجباری، بدون کلید خارجی) از حساب تأییدکننده/عامل، وگرنه قدیمی‌ترین کاربر فعال (دستور کاربر).
    """
    cur.execute(
        f"SELECT TOP 1 {n.c('users', 'user_id')} AS UserId, {n.c('users', 'username')} AS Username "
        f"FROM {n.t('users')} WHERE {n.c('users', 'emp_no')} = %(e)s "
        f"ORDER BY {n.c('users', 'is_active')} DESC, {n.c('users', 'creation_date')}",
        {"e": requester_emp_no},
    )
    row = cur.fetchone()
    if row:
        return str(row["UserId"]), row["Username"]
    user_id, _ = _resolve_kara_user(cur, n, others)
    return user_id, str(requester_emp_no)


# ---------- ثبت درخواست ----------


def submit_extra_columns(cur, n: KaraNames, requester_emp_no: int, approver_emp_no: int | None, duration) -> dict:
    """
    ستون‌های اضافه‌ای که کاراوب هنگام ثبت درخواست پر می‌کند را به‌صورت {نام ستون: مقدار} برمی‌گرداند.
    ورودی: کد پرسنلی درخواست‌دهنده و تأییدکننده، مدت درخواست. فقط ستون‌های نگاشت‌شده برگردانده می‌شوند.
    """
    values = {
        "submitted_by": requester_emp_no,
        "requested_time": str(duration),
        "duty_tools": "",
        "duty_tamin": "",
    }
    columns = {n.raw("wf_requests", role): value for role, value in values.items() if n.has("wf_requests", role)}  # فقط نگاشت‌شده‌ها
    # واحد جاری درخواست = واحد تأییدکننده
    if n.has("wf_requests", "cur_section"):
        columns[n.raw("wf_requests", "cur_section")] = get_sec_no(cur, n, approver_emp_no)
    return columns


# ---------- کسر روزانه مرخصی استحقاقی ----------


def _kasr_minutes(row: dict | None, thursday: bool) -> int | None:
    """
    دقیقه‌ی کسر مرخصی استحقاقی یک روز را از ردیف شیفت (ShiftNo/KasrGh/KasrGh5) حساب می‌کند.
    None یعنی «از این منبع اطلاعاتی نیامد»؛ ۰ یعنی روز غیرکاری.
    """
    if not row or row.get("ShiftNo") is None:
        return None
    if row.get("KasrGh") is None:
        return 0  # شیفت غیرکاری/تعطیل (در جدول شیفت‌ها تعریف نشده)
    return _hhmm_to_minutes(row["KasrGh5"] if thursday else row["KasrGh"])


def _day_deduction_minutes(cur, n: KaraNames, emp_no: int, day: date) -> int:
    """
    دقیقه‌ی کسر مرخصی استحقاقی برای یک روز از شیفت همان روز را برمی‌گرداند.
    منابع به ترتیب: کارکرد روزانه، تقویم شیفت گروهی (ماه‌های آینده)، آخرین شیفت ثبت‌شده‌ی فرد؛
    هر منبع فقط اگر نگاشت شده باشد. در نهایت قاعده‌ی روز هفته (جمعه ۰، پنجشنبه ۲۴۰، بقیه ۴۸۰).
    """
    thursday = day.weekday() == _THURSDAY
    jalali = _jalali_int(day)

    if n.has("shifts"):
        shifts, sh_no = n.t("shifts"), n.c("shifts", "shift_no")
        kasr = f"s.{n.c('shifts', 'kasr_gh')} AS KasrGh, s.{n.c('shifts', 'kasr_gh5')} AS KasrGh5"  # ستون‌های کسر شیفت

        # ۱) کارکرد روزانه‌ی کاراوب: شماره‌ی شیفت روز -> کسر آن شیفت
        if n.has("daily_work"):
            W = lambda role: n.c("daily_work", role)  # noqa: E731
            cur.execute(
                f"SELECT TOP 1 w.{W('shift_no')} AS ShiftNo, {kasr} "
                f"FROM {n.t('daily_work')} w LEFT JOIN {shifts} s ON s.{sh_no} = w.{W('shift_no')} "
                f"WHERE w.{W('emp_no')} = %(e)s AND w.{W('date')} = %(d)s",
                {"e": emp_no, "d": jalali},
            )
            minutes = _kasr_minutes(cur.fetchone(), thursday)
            if minutes is not None:
                return minutes

        # ۲) کارکرد روزانه فقط تا آخر ماه جاری ساخته می‌شود؛ برای ماه‌های آینده از تقویم
        # شیفت گروهی کاراوب: گروه فرد در آن تاریخ -> شیفت آن روز گروه (ستون روز ماه)
        if n.has("grp_shift") and n.has("emp_grps"):
            j_year, j_month, j_day = jalali // 10000, (jalali // 100) % 100, jalali % 100
            day_col = quote_mssql(f"{n.raw('grp_shift', 'day_prefix')}{j_day}")
            G = lambda role: n.c("grp_shift", role)  # noqa: E731
            E = lambda role: n.c("emp_grps", role)  # noqa: E731
            cur.execute(
                f"SELECT TOP 1 g.{day_col} AS ShiftNo, {kasr} "
                f"FROM {n.t('grp_shift')} g LEFT JOIN {shifts} s ON s.{sh_no} = g.{day_col} "
                f"WHERE g.{G('year')} = %(y)s AND g.{G('month')} = %(m)s AND g.{G('grp_no')} = ("
                f"SELECT TOP 1 e.{E('new_grp_no')} FROM {n.t('emp_grps')} e "
                f"WHERE e.{E('emp_no')} = %(e)s AND e.{E('date')} <= %(d)s ORDER BY e.{E('date')} DESC)",
                {"y": j_year, "m": j_month, "e": emp_no, "d": jalali},
            )
            minutes = _kasr_minutes(cur.fetchone(), thursday)
            if minutes is not None:
                return minutes

    # ۳) جمعه غیرکاری است؛ وگرنه کسرِ آخرین شیفت ثبت‌شده‌ی فرد در کارکرد روزانه
    if day.weekday() == _FRIDAY:
        return 0
    if n.has("shifts") and n.has("daily_work"):
        W = lambda role: n.c("daily_work", role)  # noqa: E731
        cur.execute(
            f"SELECT TOP 1 w.{W('shift_no')} AS ShiftNo, s.{n.c('shifts', 'kasr_gh')} AS KasrGh, "
            f"s.{n.c('shifts', 'kasr_gh5')} AS KasrGh5 FROM {n.t('daily_work')} w "
            f"JOIN {n.t('shifts')} s ON s.{n.c('shifts', 'shift_no')} = w.{W('shift_no')} "
            f"WHERE w.{W('emp_no')} = %(e)s ORDER BY w.{W('date')} DESC",
            {"e": emp_no},
        )
        minutes = _kasr_minutes(cur.fetchone(), thursday)
        if minutes is not None:
            return minutes
    return 240 if thursday else 480  # پیش‌فرض: پنجشنبه ۴ ساعت، بقیه ۸ ساعت


def shift_window_sync(cur, n: KaraNames, emp_no: int, day: date) -> dict | None:
    """
    بازه‌ی شیفت یک روزِ پرسنل برای محدودیت مرخصی ساعتی و مجوز خروج (docs/leave-requests.md).
    منابع به همان ترتیب کسر مرخصی: کارکرد روزانه‌ی همان تاریخ، وگرنه تقویم شیفت گروهی (EmpGrps → GrpShift).
    ردیفی که شماره‌ی شیفتش در جدول شیفت‌ها نیست (مثل ۵۰۱ = استراحت/جمعه) روز غیرکاری است.
    خروجی: خروجی shift_window (+ shift_no) یا None اگر از هیچ منبعی پیدا نشد یا ستون‌های ساعت نگاشت نشده‌اند.
    """
    from app.core.leave_request_rules import shift_window

    roles = ("start_time", "start_time5", "end_time", "end_time5", "added_day", "added_day5")
    if not n.has("shifts") or not all(n.has("shifts", r) for r in roles):
        return None
    thursday = day.weekday() == _THURSDAY
    jalali = _jalali_int(day)
    S = lambda role: n.c("shifts", role)  # noqa: E731
    sh_no = S("shift_no")
    sfx = "5" if thursday else ""
    cols = (
        f"s.{sh_no} AS Found, s.{S('start_time' + sfx)} AS StartT, s.{S('end_time' + sfx)} AS EndT, "
        f"s.{S('added_day' + sfx)} AS Added"
    )
    kasr_role = "kasr_gh5" if thursday else "kasr_gh"
    cols += f", s.{S(kasr_role)} AS Kasr" if n.has("shifts", kasr_role) else ", NULL AS Kasr"

    def _from_row(row):
        if not row or row.get("ShiftNo") is None:
            return None
        if row.get("Found") is None:
            return {"off_day": True, "shift_no": int(row["ShiftNo"])}
        w = shift_window(row.get("StartT"), row.get("EndT"), row.get("Added"), row.get("Kasr"))
        if w is not None:
            w["shift_no"] = int(row["ShiftNo"])
        return w

    if n.has("daily_work"):
        W = lambda role: n.c("daily_work", role)  # noqa: E731
        cur.execute(
            f"SELECT TOP 1 w.{W('shift_no')} AS ShiftNo, {cols} "
            f"FROM {n.t('daily_work')} w LEFT JOIN {n.t('shifts')} s ON s.{sh_no} = w.{W('shift_no')} "
            f"WHERE w.{W('emp_no')} = %(e)s AND w.{W('date')} = %(d)s",
            {"e": emp_no, "d": jalali},
        )
        row = cur.fetchone()
        if row and row.get("ShiftNo") is not None:
            return _from_row(row)

    if n.has("grp_shift") and n.has("emp_grps"):
        j_year, j_month, j_day = jalali // 10000, (jalali // 100) % 100, jalali % 100
        day_col = quote_mssql(f"{n.raw('grp_shift', 'day_prefix')}{j_day}")
        G = lambda role: n.c("grp_shift", role)  # noqa: E731
        E = lambda role: n.c("emp_grps", role)  # noqa: E731
        cur.execute(
            f"SELECT TOP 1 g.{day_col} AS ShiftNo, {cols} "
            f"FROM {n.t('grp_shift')} g LEFT JOIN {n.t('shifts')} s ON s.{sh_no} = g.{day_col} "
            f"WHERE g.{G('year')} = %(y)s AND g.{G('month')} = %(m)s AND g.{G('grp_no')} = ("
            f"SELECT TOP 1 e.{E('new_grp_no')} FROM {n.t('emp_grps')} e "
            f"WHERE e.{E('emp_no')} = %(e)s AND e.{E('date')} <= %(d)s ORDER BY e.{E('date')} DESC)",
            {"y": j_year, "m": j_month, "e": emp_no, "d": jalali},
        )
        return _from_row(cur.fetchone())
    return None


def _mor_mam_amounts(cur, n: KaraNames, emp_no: int, card_no: int, start: date, end: date):
    """
    مقادیر (Requested, StandardRequested, Inc_Type) ردیف Mor_Mam را مثل کاراوب حساب می‌کند.
    مرخصی استحقاقی: منفیِ مجموع کسر روزها (HHMM و دقیقه) و Inc_Type=0؛ بقیه: تعداد روز تقویمی و Inc_Type=NULL.
    """
    if card_no in ENTITLEMENT_CARDS:
        # جمع دقیقه‌ی کسر همه‌ی روزهای بازه
        total = 0
        day = start
        while day <= end:
            total += _day_deduction_minutes(cur, n, emp_no, day)
            day += timedelta(days=1)
        return -_minutes_to_hhmm(total), -total, 0
    days = (end - start).days + 1
    return days, days, None


# ---------- تأیید نهایی ----------


def _set_accept_code(cur, n: KaraNames, request_id: int, accept: int | None, cur_section: int | None = None) -> None:
    """AcceptCode (و در صورت وجود CurSection) درخواست را به‌روز می‌کند؛ فقط ستون‌های نگاشت‌شده."""
    sets, params = [], {"r": request_id}
    if n.has("wf_requests", "accept_code"):
        sets.append(f"{n.c('wf_requests', 'accept_code')} = %(a)s")
        params["a"] = accept
    if n.has("wf_requests", "cur_section") and cur_section is not None:
        sets.append(f"{n.c('wf_requests', 'cur_section')} = %(s)s")
        params["s"] = cur_section
    if not sets:
        return
    cur.execute(f"UPDATE {n.requests_table} SET {', '.join(sets)} WHERE {n.requests_id} = %(r)s", params)


def is_exit_permit(request: dict) -> bool:
    """
    «مجوز خروج» (برگه‌ی خروج حراست، کارت ۳۰۷/ActionId ۱۴ کاراوب): یک ساعت (StartHour = EndHour) با مدت صفر.
    مرخصی ساعتی هرگز مدت صفر ندارد. این درخواست فقط ساعت خروج است و روی تردد، Mor_Mam و کارکرد اثری ندارد؛
    کاراوب هم با تأیید فقط AcceptCode=0 می‌نویسد.
    """
    start, end = request.get("StartHour"), request.get("EndHour")
    return start is not None and start == end and str(request.get("Duration") or "0").strip() in ("0", "")


def apply_on_approval(cur, n: KaraNames, request: dict, approver_emp_no: int, app_id: int, branch_code: int) -> int:
    """
    اثر تأیید نهایی یک درخواست مرخصی/ماموریت را مثل کاراوب اعمال می‌کند.
    ورودی: ردیف خام درخواست (از _select_requests_sync)، کد پرسنلی تأییدکننده، شناسه‌ی برنامه و کد شعبه.
    خروجی: AcceptCode نهایی (۰ اعمال‌شده، ۸ تأییدشده بدون تردد) یا None اگر جدول‌های لازم نگاشت نشده باشند.
    """
    if is_exit_permit(request):  # مجوز خروج: مثل کاراوب فقط AcceptCode=0، بدون نوشتن در تردد/کارکرد
        _set_accept_code(cur, n, request["RequestId"], ACCEPT_APPLIED, get_sec_no(cur, n, approver_emp_no))
        return ACCEPT_APPLIED
    emp_no = int(request["EmpNo"])
    card_no = int(request["CardNo"])
    hourly = request.get("StartHour") is not None  # درخواست ساعتی StartHour دارد
    # اگر جدول‌های لازم برای این نوع درخواست نگاشت نشده باشند، هیچ اثری نوشته نمی‌شود
    if (hourly and not n.can_write_hourly) or (not hourly and not n.can_write_daily):
        return None
    user_id, username = _log_user(cur, n, emp_no, [approver_emp_no])
    now, today_j, now_hhmm = _now_parts()
    start = _to_date(request["StartDate"])

    # ساعتی: علامت روی تردد؛ روزانه: ردیف Mor_Mam
    if hourly:
        accept = _apply_hourly(cur, n, request, emp_no, card_no, start, user_id, username, app_id, today_j, now_hhmm)
    else:
        end = _to_date(request.get("EndDate")) or start  # درخواست یک‌روزه EndDate ندارد
        _insert_mor_mam(
            cur, n, request, emp_no, card_no, start, end, user_id, username, app_id, now, today_j, branch_code
        )
        accept = ACCEPT_APPLIED

    _set_accept_code(cur, n, request["RequestId"], accept, get_sec_no(cur, n, approver_emp_no))
    return accept


def punch_tolerance(n: KaraNames) -> int:
    """تلرانس (دقیقه) تطبیق تردد با درخواست ساعتی از تنظیمات مرخصی/ماموریت سایت در پرتال (مثل WF_TL کاراوب)."""
    try:
        return max(0, int(getattr(n.leave, "punch_tolerance_minutes", 0) or 0))
    except (TypeError, ValueError):
        return 0


def _find_hourly_punch(cur, n: KaraNames, emp_no: int, day: date, start: int, end: int, extra: str = "", params=None):
    """
    تردد مطابق یک درخواست ساعتی، مثل کاراوب (درخواست‌های ۱۷۱ و ۱۸۳): ترددهای بازه‌ی [شروع − تلرانس، پایان + تلرانس]
    و از بین آن‌ها اولین تردد. بازه‌ی عبوری از نیمه‌شب (EndHour < StartHour) و
    تلرانسی که به روز قبل/بعد برسد هم پوشش داده می‌شود (تردد بامداد با تاریخ تقویمی روز بعد در DataFile است).
    extra: شرط اضافه روی تردد (مثلاً Status = ۰ یا Status = کارت) با پارامترهایش در params.
    خروجی: (تردد یا None، تاریخ میلادی همان تردد).
    """
    tol = punch_tolerance(n)
    s_min = _hhmm_to_minutes(start)
    e_min = _hhmm_to_minutes(end)
    if e_min < s_min:
        e_min += 1440
    lo, hi = s_min - tol, e_min + tol
    days = [day + timedelta(days=k) for k in (-1, 0, 1) if lo < 0 or k >= 0]
    days = [d for d in days if (d - day).days * 1440 <= hi and (d - day).days * 1440 + 1439 >= lo]
    date_ints = [_jalali_int(d) for d in days]
    placeholders = ", ".join(f"%(d{i})s" for i in range(len(date_ints)))
    params = {**dict(params or {}), "e": emp_no, **{f"d{i}": v for i, v in enumerate(date_ints)}}
    cur.execute(
        f"SELECT {n.c('datafile', 'id')} AS Id, {n.df_date} AS DateInt, {n.df_time} AS Time, "
        f"{n.c('datafile', 'status')} AS Status, {n.c('datafile', 'duration')} AS Duration, "
        f"{n.c('datafile', 'prev_day')} AS PrevDay, {n.c('datafile', 'application_id')} AS ApplicationId, "
        f"{n.c('datafile', 'branch_code')} AS BranchCode FROM {n.df_table} "
        f"WHERE {n.df_emp_no} = %(e)s AND {n.df_date} IN ({placeholders}) {extra}",
        params,
    )
    by_int = dict(zip(date_ints, days, strict=True))
    best = None
    for row in cur.fetchall():
        d = by_int.get(int(row["DateInt"]))
        if d is None:
            continue
        t = (d - day).days * 1440 + _hhmm_to_minutes(int(row["Time"]))
        if not lo <= t <= hi:
            continue
        if best is None or t < best[0]:  # اولین تردد بازه (کاراوب در ۱۷۱ خروج ۰۹:۱۲ را گرفت، نه بازگشت ۱۰:۰۵)
            best = (t, row, d)
    if best is None:
        return None, day
    return best[1], best[2]


def _hhmm_to_minutes(hhmm: int) -> int:
    hour, minute = divmod(int(hhmm), 100)
    return hour * 60 + minute


def _set_io_time(cur, n: KaraNames, request_id: int, io_time: int | None, tolerance: int | None) -> None:
    """IOTime (ساعت تردد مطابق) و Tolerance درخواست را مثل کاراوب می‌نویسد؛ None هر دو را پاک می‌کند."""
    sets, params = [], {"r": request_id}
    if n.has("wf_requests", "io_time"):
        sets.append(f"{n.c('wf_requests', 'io_time')} = %(io)s")
        params["io"] = io_time
    if n.has("wf_requests", "tolerance"):
        sets.append(f"{n.c('wf_requests', 'tolerance')} = %(tl)s")
        params["tl"] = tolerance
    if sets:
        cur.execute(f"UPDATE {n.requests_table} SET {', '.join(sets)} WHERE {n.requests_id} = %(r)s", params)


def _shift_ref(cur, n: KaraNames, emp_no: int, day: date, s_min: int, e_min: int):
    """
    شیفت مرجع یک درخواست ساعتی روی محور دقیقه نسبت به ۰۰:۰۰ همان روز: شیفت همان روز یا شیفت شبِ روز قبل (برای ردیف
    بامدادی با تاریخ روز بعد)، هرکدام بیشترین هم‌پوشانی را دارد (وگرنه نزدیک‌ترین).
    خروجی: (ws, we) یا "off" (روز غیرکاری) یا None (شیفت نامعلوم).
    """
    found, candidates = False, []
    for offset in (0, -1):
        window = shift_window_sync(cur, n, emp_no, day + timedelta(days=offset))
        if window is None:
            continue
        found = True
        if window.get("off_day"):
            if offset == 0:
                candidates.append(("off", 0, 10**6))
            continue
        ws = offset * 1440 + _hhmm_to_minutes(window["start"])
        we = offset * 1440 + _hhmm_to_minutes(window["end"] % 2400) + (1440 if window["end"] >= 2400 else 0)
        overlap = min(e_min, we) - max(s_min, ws)
        distance = 0 if overlap > 0 else max(ws - e_min, s_min - we)
        candidates.append(((ws, we), overlap, distance))
    if not found:
        return None
    if not candidates:
        return "off"
    with_overlap = [c for c in candidates if c[0] != "off" and c[1] > 0]
    if with_overlap:
        return max(with_overlap, key=lambda c: c[1])[0]
    return min(candidates, key=lambda c: c[2])[0]


def _match_hourly_punch(cur, n: KaraNames, emp_no: int, day: date, s_min: int, e_min: int, ref):
    """
    تردد مطابق درخواست ساعتی، مطابق قاعده‌ی تلرانس کاراوب (ورود و خروج تا «تلرانس» دقیقه قبل/بعد از ساعت درخواست):
    - خروجِ نزدیک ساعت شروع (|t − شروع| ≤ تلرانس)، مثل ۱۷۱ (خروج ۰۹:۱۲ برای ۰۹:۰۰) و ۱۸۳ (خروج ۱۱:۵۳ برای ۱۲:۰۰)؛
    - وگرنه ورودِ نزدیک ساعت پایان (مرخصی اول وقت: ورود ۱۲:۰۱ برای ۰۶:۳۰–۱۲:۰۰).
    ورودی که نزدیک شروع است یعنی شخص سر کار آمده (درخواست ۱۰۲: ورود ۰۶:۲۳ برای مرخصی ۰۶:۳۰) و علامت نمی‌خورد.
    ورود/خروج بودن هر تردد از ترتیبش در بازه‌ی شیفت (شیفت −۳ ساعت تا +۶ ساعت؛ شیفت نامعلوم: همان روز) تعیین می‌شود:
    اولی ورود، دومی خروج، ... خروجی: (تردد یا None، تاریخ میلادی تردد).
    """
    tol = punch_tolerance(n)
    lo, hi = (ref[0] - 180, ref[1] + 360) if isinstance(ref, tuple) else (0, 1439)
    days = [day + timedelta(days=k) for k in (-1, 0, 1)]
    days = [d for d in days if (d - day).days * 1440 <= hi and (d - day).days * 1440 + 1439 >= lo]
    date_ints = [_jalali_int(d) for d in days]
    placeholders = ", ".join(f"%(d{i})s" for i in range(len(date_ints)))
    cur.execute(
        f"SELECT {n.c('datafile', 'id')} AS Id, {n.df_date} AS DateInt, {n.df_time} AS Time, "
        f"{n.c('datafile', 'status')} AS Status, {n.c('datafile', 'duration')} AS Duration, "
        f"{n.c('datafile', 'prev_day')} AS PrevDay, {n.c('datafile', 'application_id')} AS ApplicationId, "
        f"{n.c('datafile', 'branch_code')} AS BranchCode FROM {n.df_table} "
        f"WHERE {n.df_emp_no} = %(e)s AND {n.df_date} IN ({placeholders})",
        {"e": emp_no, **{f"d{i}": v for i, v in enumerate(date_ints)}},
    )
    by_int = dict(zip(date_ints, days, strict=True))
    punches = []
    for row in cur.fetchall():
        d = by_int.get(int(row["DateInt"]))
        if d is None:
            continue
        t = (d - day).days * 1440 + _hhmm_to_minutes(int(row["Time"]))
        if lo <= t <= hi:
            punches.append((t, row, d))
    punches.sort(key=lambda x: x[0])
    exits = [(abs(t - s_min), t, row, d) for i, (t, row, d) in enumerate(punches) if i % 2 == 1 and abs(t - s_min) <= tol]
    entries = [(abs(t - e_min), t, row, d) for i, (t, row, d) in enumerate(punches) if i % 2 == 0 and abs(t - e_min) <= tol]
    for group in (exits, entries):
        if group:
            best = min(group, key=lambda x: (x[0], x[1]))
            return best[2], best[3]
    return None, day


def _apply_hourly(cur, n, request, emp_no, card_no, day, user_id, username, app_id, today_j, now_hhmm) -> int:
    """
    اثر درخواست ساعتی: ترددِ مطابق (_match_hourly_punch) علامت کارت و مدت درخواست را می‌گیرد.
    مرخصی (نه مأموریت): فقط بخشِ داخل ساعت رسمی شیفت حساب می‌شود (دستور کاربر) — کاملاً خارج از شیفت یا روز غیرکاری
    علامت نمی‌خورد؛ بخشی خارج: مدت به بخش داخل شیفت کوتاه و تطبیق با همان بخش انجام می‌شود. شیفت نامعلوم: بدون محدودیت.
    اگر تردد مطابق از قبل علامت دارد (کارت روی دستگاه یا درخواست دیگر)، کاراوب حسابش کرده و چیزی تغییر نمی‌کند.
    خروجی: ACCEPT_APPLIED اگر اعمال شد، وگرنه ACCEPT_APPROVED_NOT_APPLIED.
    """
    s_min = _hhmm_to_minutes(int(request["StartHour"]))
    e_min = _hhmm_to_minutes(int(request["EndHour"]))
    if e_min < s_min:
        e_min += 1440  # عبور از نیمه‌شب
    try:  # مدت درخواست رشته است؛ مقدار نامعتبر = ۰
        new_duration = int(request.get("Duration") or 0)
    except (TypeError, ValueError):
        new_duration = 0
    ref = _shift_ref(cur, n, emp_no, day, s_min, e_min)
    if request.get("OperationsID") != MISSION_OPERATION_ID and ref is not None:
        if ref == "off":
            return ACCEPT_APPROVED_NOT_APPLIED  # روز غیرکاری
        a, b = max(s_min, ref[0]), min(e_min, ref[1])
        if b <= a:
            return ACCEPT_APPROVED_NOT_APPLIED  # مرخصی کاملاً خارج از شیفت
        if (a, b) != (s_min, e_min):
            s_min, e_min = a, b
            new_duration = ((b - a) // 60) * 100 + (b - a) % 60
    punch, day = _match_hourly_punch(cur, n, emp_no, day, s_min, e_min, ref)
    if not punch or int(punch.get("Status") or 0) != 0:
        return ACCEPT_APPROVED_NOT_APPLIED
    _update_punch(cur, n, punch, emp_no, day, card_no, new_duration, user_id, username, app_id, today_j, now_hhmm)
    _set_io_time(cur, n, request["RequestId"], int(punch["Time"]), punch_tolerance(n))
    return ACCEPT_APPLIED


def _update_punch(
    cur, n, punch, emp_no, day, new_status, new_duration, user_id, username, app_id, today_j, now_hhmm, restore=False
):
    """
    Status/Duration/ApplicationId یک تردد را تغییر می‌دهد و یک ردیف LogDataFile می‌نویسد.
    restore=True هنگام لغو اثر: ApplicationId تردد به منبع اولیه‌اش برمی‌گردد تا پرچم «گردش کار» روی تردد نماند.
    """
    source_app_id = int(punch["ApplicationId"]) & 0xFFFF  # ۱۶ بیت پایین = منبع اولیه‌ی تردد (دستگاه/برنامه)
    # ردیف لاگ همیشه با پرچم «گردش کار» ثبت می‌شود (مثل کاراوب)
    log_app_id = (app_id << _EDITOR_SHIFT) | source_app_id
    # روی خودِ تردد: هنگام لغو، منبع اولیه؛ هنگام اعمال، پرچم گردش کار
    punch_app_id = source_app_id if restore else log_app_id
    cur.execute(
        f"UPDATE {n.df_table} SET {n.c('datafile', 'status')} = %(st)s, {n.c('datafile', 'duration')} = %(du)s, "
        f"{n.c('datafile', 'application_id')} = %(ap)s, {n.c('datafile', 'checksum')} = 0 "
        f"WHERE {n.c('datafile', 'id')} = %(id)s",
        {"st": new_status, "du": new_duration, "ap": punch_app_id, "id": punch["Id"]},
    )
    if not n.has("log_datafile"):
        return  # لاگ تغییر تردد نگاشت نشده
    # ردیف لاگ تغییر: ساعت و PrevDay بدون تغییر، Duration و Status قدیم/جدید
    L = lambda role: n.c("log_datafile", role)  # noqa: E731
    cur.execute(
        f"INSERT INTO {n.t('log_datafile')} ({L('user_id')}, {L('application_id')}, {L('username')}, "
        f"{L('additional_info')}, {L('edit_date')}, {L('edit_time')}, {L('io_date')}, {L('emp_no')}, "
        f"{L('old_time')}, {L('new_time')}, {L('old_duration')}, {L('new_duration')}, {L('old_status')}, "
        f"{L('new_status')}, {L('old_prev_day')}, {L('new_prev_day')}, {L('old_vt')}, {L('new_vt')}, "
        f"{L('old_ac')}, {L('new_ac')}, {L('branch_code')}) VALUES "
        "(%(u)s, %(ap)s, %(un)s, '', %(ed)s, %(et)s, %(io)s, %(e)s, %(tm)s, %(tm)s, %(od)s, %(nd)s, %(os)s, "
        "%(ns)s, %(pd)s, %(pd)s, NULL, NULL, NULL, NULL, %(b)s)",
        {
            "u": user_id,
            "ap": log_app_id,
            "un": username,
            "ed": today_j,
            "et": now_hhmm,
            "io": _jalali_int(day),
            "e": emp_no,
            "tm": punch["Time"],
            "od": punch["Duration"],
            "nd": new_duration,
            "os": punch["Status"],
            "ns": new_status,
            "pd": punch["PrevDay"],
            "b": punch["BranchCode"],
        },
    )


def _insert_mor_mam(cur, n, request, emp_no, card_no, start, end, user_id, username, app_id, now, today_j, branch_code):
    """یک ردیف مرخصی/ماموریت روزانه در Mor_Mam درج می‌کند و لاگ درج (ChangeType=1) می‌نویسد."""
    requested, standard, inc_type = _mor_mam_amounts(cur, n, emp_no, card_no, start, end)
    # پارامترهای ردیف؛ همین دیکشنری برای لاگ هم استفاده می‌شود
    row = {
        "e": emp_no,
        "sd": _jalali_int(start),
        "sds": datetime(start.year, start.month, start.day),
        "ed": _jalali_int(end),
        "eds": datetime(end.year, end.month, end.day),
        "rq": requested,
        "sr": standard,
        "is": today_j,
        "ty": card_no,
        "bb": request.get("Description") or "",
        "it": inc_type,
        "u": user_id,
        "now": now,
        "b": branch_code,
    }
    M = lambda role: n.c("mor_mam", role)  # noqa: E731
    cur.execute(
        f"INSERT INTO {n.t('mor_mam')} ({M('emp_no')}, {M('s_date')}, {M('s_date_standard')}, {M('e_date')}, "
        f"{M('e_date_standard')}, {M('requested')}, {M('standard_requested')}, {M('serial_number')}, "
        f"{M('issue_date')}, {M('type')}, {M('babat')}, {M('inc_type')}, {M('user_id')}, {M('last_modify_date')}, "
        f"{M('checksum')}, {M('branch_code')}) OUTPUT INSERTED.{M('ref_number')} AS RefNumber VALUES "
        "(%(e)s, %(sd)s, %(sds)s, %(ed)s, %(eds)s, %(rq)s, %(sr)s, '', %(is)s, %(ty)s, %(bb)s, %(it)s, %(u)s, "
        "%(now)s, 0, %(b)s)",
        row,
    )
    ref_number = cur.fetchone()["RefNumber"]  # شناسه‌ی ردیف تازه از OUTPUT INSERTED
    _log_mor_mam(cur, n, row, ref_number, change_type=1, username=username, app_id=app_id)


def _log_mor_mam(cur, n: KaraNames, row: dict, ref_number, change_type: int, username: str, app_id: int) -> None:
    """یک ردیف LogMorMam برای درج (ChangeType=1) یا حذف (ChangeType=3) ردیف Mor_Mam می‌نویسد."""
    if not n.has("log_mor_mam"):
        return  # لاگ مرخصی/ماموریت روزانه نگاشت نشده
    L = lambda role: n.c("log_mor_mam", role)  # noqa: E731
    cur.execute(
        f"INSERT INTO {n.t('log_mor_mam')} ({L('user_id')}, {L('application_id')}, {L('username')}, "
        f"{L('additional_info')}, {L('change_date')}, {L('change_type')}, {L('ref_number')}, {L('emp_no')}, "
        f"{L('s_date')}, {L('s_date_standard')}, {L('e_date')}, {L('e_date_standard')}, {L('requested')}, "
        f"{L('standard_requested')}, {L('serial_number')}, {L('issue_date')}, {L('type')}, {L('babat')}, "
        f"{L('inc_type')}, {L('branch_code')}) VALUES (%(u)s, %(ap)s, %(un)s, '', %(now)s, %(ct)s, %(ref)s, "
        "%(e)s, %(sd)s, %(sds)s, %(ed)s, %(eds)s, %(rq)s, %(sr)s, '', %(is)s, %(ty)s, %(bb)s, %(it)s, %(b)s)",
        {**row, "ap": app_id, "un": username, "ct": change_type, "ref": ref_number, "now": kara_now()},
    )


# ---------- لغو اثر ----------


def apply_pending_hourly(cur, n: KaraNames, request: dict, app_id: int) -> bool:
    """
    اعمالِ بعدیِ یک درخواست ساعتیِ تأییدشده که هنوز به ترددی وصل نشده (AcceptCode = ۸)، مثل کاراوب (درخواست ۱۷۱: تأیید
    قبل از خروج، اعمال بعد از ثبت تردد). Job زمان‌بندی‌شده‌ی پرتال صدا می‌زند. خروجی: True اگر اعمال شد.
    """
    if is_exit_permit(request) or request.get("StartHour") is None or not n.can_write_hourly:
        return False
    if n.has("wf_requests", "accept_code"):  # شاید در این فاصله در کاراوب یا پرتال تغییر کرده باشد
        cur.execute(
            f"SELECT {n.c('wf_requests', 'accept_code')} AS AcceptCode FROM {n.requests_table} "
            f"WHERE {n.requests_id} = %(r)s",
            {"r": request["RequestId"]},
        )
        state = cur.fetchone()
        if not state or state.get("AcceptCode") != ACCEPT_APPROVED_NOT_APPLIED:
            return False
    emp_no = int(request["EmpNo"])
    approver = request.get("ApprovalByManagerEmpNo") or request.get("CurEmpNo")
    user_id, username = _log_user(cur, n, emp_no, [approver])
    _, today_j, now_hhmm = _now_parts()
    accept = _apply_hourly(
        cur, n, request, emp_no, int(request["CardNo"]), _to_date(request["StartDate"]),
        user_id, username, app_id, today_j, now_hhmm,
    )
    if accept != ACCEPT_APPLIED:
        return False
    _set_accept_code(cur, n, request["RequestId"], ACCEPT_APPLIED)
    return True


def revert_effects(cur, n: KaraNames, request: dict, actor_emp_no: int | None, app_id: int) -> None:
    """
    اثر یک درخواستِ تأییدشده را از کارکرد کاراوب برمی‌دارد (هنگام رد، حذف یا ویرایش مدیریتی).
    ساعتی: Status تردد به مقدار قبل از اعمال برمی‌گردد + لاگ؛ روزانه: ردیف Mor_Mam حذف + لاگ (ChangeType=3).
    اگر اثری ثبت نشده بود یا جدول‌ها نگاشت نشده باشند، کاری نمی‌کند.
    """
    if is_exit_permit(request):  # مجوز خروج اثری روی تردد/کارکرد نگذاشته بود
        return
    emp_no = int(request["EmpNo"])
    card_no = int(request["CardNo"])
    start = _to_date(request["StartDate"])
    hourly = request.get("StartHour") is not None
    if (hourly and not n.can_write_hourly) or (not hourly and not n.can_write_daily):
        return
    user_id, username = _log_user(cur, n, emp_no, [actor_emp_no, request.get("ApprovalByManagerEmpNo")])
    now, today_j, now_hhmm = _now_parts()

    if hourly:
        # فقط اگر درخواست واقعاً روی ترددی اعمال شده بود (AcceptCode = 0)
        if n.has("wf_requests", "accept_code"):
            cur.execute(
                f"SELECT {n.c('wf_requests', 'accept_code')} AS AcceptCode FROM {n.requests_table} "
                f"WHERE {n.requests_id} = %(r)s",
                {"r": request["RequestId"]},
            )
            state = cur.fetchone()
            if not state or state.get("AcceptCode") != ACCEPT_APPLIED:
                return  # روی ترددی اعمال نشده بود
        # ترددی در بازه‌ی درخواست که علامت همین کارت را دارد
        punch, punch_day = _find_hourly_punch(
            cur, n, emp_no, start, int(request["StartHour"]), int(request["EndHour"]),
            f"AND {n.c('datafile', 'status')} = %(c)s ", {"c": card_no},
        )
        if punch:
            # وضعیت/مدتِ قبل از اعمال از آخرین لاگ همین پرتال (پرچم گردش کار) خوانده می‌شود؛
            # اگر تردد از اول با کارت مرخصی/ماموریت از خودِ دستگاه زده شده بود، آن علامت واقعی پاک نمی‌شود
            before = {}
            if n.has("log_datafile"):
                L = lambda role: n.c("log_datafile", role)  # noqa: E731
                cur.execute(
                    f"SELECT TOP 1 {L('old_status')} AS OldStatus, {L('old_duration')} AS OldDuration "
                    f"FROM {n.t('log_datafile')} WHERE {L('emp_no')} = %(e)s AND {L('io_date')} = %(d)s "
                    f"AND {L('old_time')} = %(t)s AND {L('new_time')} = %(t)s AND {L('new_status')} = %(c)s "
                    f"AND ({L('application_id')} & %(flag)s) <> 0 ORDER BY {L('id')} DESC",
                    {
                        "e": emp_no,
                        "d": _jalali_int(punch_day),
                        "t": punch["Time"],
                        "c": card_no,
                        "flag": app_id << _EDITOR_SHIFT,
                    },
                )
                before = cur.fetchone() or {}
            _update_punch(
                cur, n, punch, emp_no, punch_day, before.get("OldStatus") or 0, before.get("OldDuration") or 0,
                user_id, username, app_id, today_j, now_hhmm, restore=True,
            )
            _set_io_time(cur, n, request["RequestId"], None, None)
        return

    # روزانه: ردیف Mor_Mam همین درخواست (همان پرسنل، بازه و کارت؛ ردیف با همان توضیح مقدم است)
    end = _to_date(request.get("EndDate")) or start
    M = lambda role: n.c("mor_mam", role)  # noqa: E731
    cur.execute(
        f"SELECT TOP 1 {M('ref_number')} AS RefNumber, {M('emp_no')} AS EmpNo, {M('s_date')} AS SDate, "
        f"{M('s_date_standard')} AS SDateStandard, {M('e_date')} AS EDate, {M('e_date_standard')} AS EDateStandard, "
        f"{M('requested')} AS Requested, {M('standard_requested')} AS StandardRequested, "
        f"{M('issue_date')} AS IssueDate, {M('type')} AS Type, {M('babat')} AS Babat, {M('inc_type')} AS IncType, "
        f"{M('branch_code')} AS BranchCode FROM {n.t('mor_mam')} "
        f"WHERE {M('emp_no')} = %(e)s AND {M('s_date')} = %(sd)s AND ISNULL({M('e_date')}, {M('s_date')}) = %(ed)s "
        f"AND {M('type')} = %(ty)s ORDER BY CASE WHEN {M('babat')} = %(bb)s THEN 0 ELSE 1 END, {M('ref_number')} DESC",
        {
            "e": emp_no,
            "sd": _jalali_int(start),
            "ed": _jalali_int(end),
            "ty": card_no,
            "bb": request.get("Description") or "",
        },
    )
    mor = cur.fetchone()
    if not mor:
        return
    # حذف ردیف و ثبت لاگ حذف با مقادیر همان ردیف
    cur.execute(f"DELETE FROM {n.t('mor_mam')} WHERE {M('ref_number')} = %(r)s", {"r": mor["RefNumber"]})
    log_row = {
        "u": user_id,
        "e": mor["EmpNo"],
        "sd": mor["SDate"],
        "sds": mor["SDateStandard"],
        "ed": mor["EDate"],
        "eds": mor["EDateStandard"],
        "rq": mor["Requested"],
        "sr": mor["StandardRequested"],
        "is": mor["IssueDate"],
        "ty": mor["Type"],
        "bb": mor["Babat"],
        "it": mor["IncType"],
        "b": mor["BranchCode"],
    }
    _log_mor_mam(cur, n, log_row, mor["RefNumber"], change_type=3, username=username, app_id=app_id)


def clear_accept_code(cur, n: KaraNames, request_id: int) -> None:
    """AcceptCode درخواست را NULL می‌کند (برگشت به وضعیت «در انتظار»)؛ اگر ستون نگاشت نشده کاری نمی‌کند."""
    if not n.has("wf_requests", "accept_code"):
        return
    accept_col = n.c("wf_requests", "accept_code")
    cur.execute(f"UPDATE {n.requests_table} SET {accept_col} = NULL WHERE {n.requests_id} = %(r)s", {"r": request_id})
    _set_io_time(cur, n, request_id, None, None)


def delete_request_state_rows(cur, n: KaraNames, request_id: int) -> None:
    """ردیف‌های وضعیت یک درخواست را حذف می‌کند؛ WF_RequestState به جدول درخواست کلید خارجی ندارد و باید دستی پاک شود."""
    if not n.has("wf_request_state"):
        return
    cur.execute(
        f"DELETE FROM {n.t('wf_request_state')} WHERE {n.c('wf_request_state', 'request_id')} = %(r)s",
        {"r": request_id},
    )


# ---------- تردد فراموش‌شده ----------
#
# رفتار کاراوب:
#   ثبت: یک ردیف درخواست به‌ازای هر تردد - StartDate = تاریخ تردد،
#        StartHour = ساعت تردد، EndHour = ۰، EndDate = NULL، Duration = '0'
#   تأیید نهایی: یک ردیف تازه در جدول تردد (Status 0، Modify 1، Direction 0،
#        ApplicationId = شناسه برنامه، DeviceNumber صریحاً NULL، Duration 0،
#        PrevDay 0، VT 0، AC 0) + یک ردیف لاگ «درج» (همه ستون‌های Old* خالی)؛
#        AcceptCode = 0
#   حذف تردد (در کاراوب): لاگ با همه ستون‌های New* خالی و ApplicationId =
#        (شناسه ویرایشگر << 16) | منبع تردد
#
# PrevDay همیشه ۰ نوشته می‌شود (مثل کاراوب) - شیفت شب با تاریخ واقعی هر
# تردد ثبت می‌شود و محاسبه کارکرد را خودِ کاراوب انجام می‌دهد.


def punch_exists(cur, n: KaraNames, emp_no: int, date_int: int, time_int: int) -> bool:
    """آیا همین تردد (همان روز و همان دقیقه) از قبل در جدول تردد هست؟"""
    if not n.has_punch_table:
        return False
    cur.execute(
        f"SELECT TOP 1 1 AS X FROM {n.df_table} WHERE {n.df_emp_no} = %(e)s AND {n.df_date} = %(d)s "
        f"AND {n.df_time} = %(t)s",
        {"e": emp_no, "d": date_int, "t": time_int},
    )
    return cur.fetchone() is not None


def apply_forgotten_punch(cur, n: KaraNames, request: dict, approver_emp_no: int, app_id: int, branch_code: int):
    """
    اثر تأیید نهایی تردد فراموش‌شده: درج تردد در جدول تردد + لاگ درج + AcceptCode = ۰.
    اگر همان تردد از قبل وجود داشته باشد فقط AcceptCode به‌روز می‌شود. خروجی: ACCEPT_APPLIED.
    """
    if not n.can_write_punch:
        raise RuntimeError("ستون‌های لازم جدول تردد برای ثبت تردد فراموش‌شده در تنظیمات سایت نگاشت نشده‌اند")
    emp_no = int(request["EmpNo"])
    day = _to_date(request["StartDate"])
    date_int = _jalali_int(day)
    time_int = int(request["StartHour"])
    user_id, username = _log_user(cur, n, emp_no, [approver_emp_no])
    _, today_j, now_hhmm = _now_parts()

    # درج تردد فقط اگر تکراری نباشد
    if not punch_exists(cur, n, emp_no, date_int, time_int):
        D = lambda role: n.c("datafile", role)  # noqa: E731
        cur.execute(
            f"INSERT INTO {n.df_table} ({n.df_emp_no}, {n.df_date}, {n.df_time}, {D('status')}, {D('modify')}, "
            f"{D('direction')}, {D('application_id')}, {D('device_number')}, {D('duration')}, {D('prev_day')}, "
            f"{D('vt')}, {D('ac')}, {D('checksum')}, {D('branch_code')}) VALUES "
            # DeviceNumber صریحاً NULL (مثل کاراوب) - پیش‌فرض دیتابیس با کلید خارجی دستگاه‌ها تداخل دارد
            "(%(e)s, %(d)s, %(t)s, 0, 1, 0, %(ap)s, NULL, 0, 0, 0, 0, 0, %(b)s)",
            {"e": emp_no, "d": date_int, "t": time_int, "ap": app_id, "b": branch_code},
        )
        _log_punch_change(
            cur, n, user_id, username, app_id, today_j, now_hhmm, date_int, emp_no, branch_code,
            old=None, new={"Time": time_int, "Duration": 0, "Status": 0, "PrevDay": 0},
        )

    _set_accept_code(cur, n, request["RequestId"], ACCEPT_APPLIED, get_sec_no(cur, n, approver_emp_no))
    return ACCEPT_APPLIED


def revert_forgotten_punch(cur, n: KaraNames, request: dict, actor_emp_no: int | None, app_id: int) -> None:
    """
    لغو اثر تردد فراموش‌شده (حذف/رد مدیریتی پس از تأیید): همان ترددی که این پرتال درج کرده بود حذف
    و لاگ حذف نوشته می‌شود. تردد دستگاه یا تردد دستیِ کاراوب هرگز پاک نمی‌شود.
    """
    if not n.can_write_punch:
        return
    # فقط اگر درخواست واقعاً اعمال شده بود
    if n.has("wf_requests", "accept_code"):
        cur.execute(
            f"SELECT {n.c('wf_requests', 'accept_code')} AS AcceptCode FROM {n.requests_table} "
            f"WHERE {n.requests_id} = %(r)s",
            {"r": request["RequestId"]},
        )
        state = cur.fetchone()
        if not state or state.get("AcceptCode") != ACCEPT_APPLIED:
            return
    emp_no = int(request["EmpNo"])
    date_int = _jalali_int(_to_date(request["StartDate"]))
    # ترددِ درج‌شده توسط همین برنامه (Modify=1 و منبع = app_id) در همان روز و دقیقه
    D = lambda role: n.c("datafile", role)  # noqa: E731
    cur.execute(
        f"SELECT TOP 1 {D('id')} AS Id, {n.df_time} AS Time, {D('status')} AS Status, {D('duration')} AS Duration, "
        f"{D('prev_day')} AS PrevDay, {D('application_id')} AS ApplicationId, {D('branch_code')} AS BranchCode "
        f"FROM {n.df_table} WHERE {n.df_emp_no} = %(e)s AND {n.df_date} = %(d)s AND {n.df_time} = %(t)s "
        f"AND {D('modify')} = 1 AND ({D('application_id')} & 65535) = %(ap)s ORDER BY {D('id')} DESC",
        {"e": emp_no, "d": date_int, "t": int(request["StartHour"]), "ap": app_id},
    )
    punch = cur.fetchone()
    if not punch:
        return
    user_id, username = _log_user(cur, n, emp_no, [actor_emp_no, request.get("ApprovalByManagerEmpNo")])
    _, today_j, now_hhmm = _now_parts()
    cur.execute(f"DELETE FROM {n.df_table} WHERE {D('id')} = %(id)s", {"id": punch["Id"]})
    log_app_id = (app_id << _EDITOR_SHIFT) | (int(punch["ApplicationId"]) & 0xFFFF)  # پرچم ویرایشگر | منبع تردد
    _log_punch_change(
        cur, n, user_id, username, log_app_id, today_j, now_hhmm, date_int, emp_no, punch["BranchCode"],
        old=punch, new=None,
    )


def _log_punch_change(cur, n, user_id, username, app_id, today_j, now_hhmm, io_date, emp_no, branch_code, old, new):
    """یک ردیف LogDataFile برای درج (old=None) یا حذف (new=None) تردد می‌نویسد؛ ستون‌های سمت خالی NULL می‌شوند."""
    if not n.has("log_datafile"):
        return
    old = old or {}
    new = new or {}
    L = lambda role: n.c("log_datafile", role)  # noqa: E731
    cur.execute(
        f"INSERT INTO {n.t('log_datafile')} ({L('user_id')}, {L('application_id')}, {L('username')}, "
        f"{L('additional_info')}, {L('edit_date')}, {L('edit_time')}, {L('io_date')}, {L('emp_no')}, "
        f"{L('old_time')}, {L('new_time')}, {L('old_duration')}, {L('new_duration')}, {L('old_status')}, "
        f"{L('new_status')}, {L('old_prev_day')}, {L('new_prev_day')}, {L('old_vt')}, {L('new_vt')}, "
        f"{L('old_ac')}, {L('new_ac')}, {L('branch_code')}) VALUES "
        "(%(u)s, %(ap)s, %(un)s, '', %(ed)s, %(et)s, %(io)s, %(e)s, %(ot)s, %(nt)s, %(od)s, %(nd)s, %(os)s, "
        "%(ns)s, %(op)s, %(np)s, NULL, NULL, NULL, NULL, %(b)s)",
        {
            "u": user_id,
            "ap": app_id,
            "un": username,
            "ed": today_j,
            "et": now_hhmm,
            "io": io_date,
            "e": emp_no,
            "ot": old.get("Time"),
            "nt": new.get("Time"),
            "od": old.get("Duration"),
            "nd": new.get("Duration"),
            "os": old.get("Status"),
            "ns": new.get("Status"),
            "op": old.get("PrevDay"),
            "np": new.get("PrevDay"),
            "b": branch_code,
        },
    )


def move_up_to(cur, n: KaraNames, request: dict, from_emp_no: int, to_emp_no: int) -> None:
    """
    ارجاع درخواست از سرپرست (from_emp_no) به مسئول نیروی انسانی (to_emp_no).
    تأییدکننده‌ی فعلی و واحد او روی درخواست عوض می‌شود و اگر جدول ارجاع نگاشت شده باشد،
    یک ردیف در آن ثبت می‌شود تا تاریخچه‌ی مسیر درخواست در خودِ کاراوب هم دیده شود.
    """
    cur_col = getattr(n.leave, "cur_emp_no_column", None)
    if not cur_col:
        raise RuntimeError("ستون تأییدکننده فعلی در نگاشت درخواست تنظیم نشده است")
    # به‌روزرسانی تأییدکننده‌ی فعلی و (در صورت نگاشت) واحد جاری
    sets, params = [f"{quote_mssql(cur_col)} = %(to)s"], {"to": to_emp_no, "r": request["RequestId"]}
    from_sec = get_sec_no(cur, n, from_emp_no)
    to_sec = get_sec_no(cur, n, to_emp_no)
    if n.has("wf_requests", "cur_section") and to_sec is not None:
        sets.append(f"{n.c('wf_requests', 'cur_section')} = %(sec)s")
        params["sec"] = to_sec
    cur.execute(f"UPDATE {n.requests_table} SET {', '.join(sets)} WHERE {n.requests_id} = %(r)s", params)

    # ردیف تاریخچه‌ی ارجاع؛ فقط ستون‌های نگاشت‌شده نوشته می‌شوند
    if not n.can_write_moveup:
        return
    values = {
        "request_id": request["RequestId"],
        "date": kara_now(),
        "from_manager": from_emp_no,
        "to_manager": to_emp_no,
        "card_no": request.get("CardNo"),
        "from_sec": from_sec,
        "to_sec": to_sec,
    }
    columns = [(n.c("wf_moveup", role), value) for role, value in values.items() if n.has("wf_moveup", role)]
    cur.execute(
        f"INSERT INTO {quote_mssql(n.leave.wf_moveup_table_name)} ({', '.join(c for c, _ in columns)}) "
        f"VALUES ({', '.join(f'%(v{i})s' for i in range(len(columns)))})",
        {f"v{i}": value for i, (_, value) in enumerate(columns)},
    )


def request_ids_moved_by(cur, n: KaraNames, from_emp_no: int) -> list[int]:
    """شناسه‌ی درخواست‌هایی که این فرد (به‌عنوان سرپرست) به مرحله‌ی بعد ارجاع داده است؛ بدون جدول ارجاع، لیست خالی."""
    if not n.can_write_moveup:
        return []
    cur.execute(
        f"SELECT DISTINCT {n.c('wf_moveup', 'request_id')} AS RequestId FROM {quote_mssql(n.leave.wf_moveup_table_name)} "
        f"WHERE {n.c('wf_moveup', 'from_manager')} = %(e)s",
        {"e": from_emp_no},
    )
    return [int(r["RequestId"]) for r in cur.fetchall()]


def reassign_current_approver(cur, n: KaraNames, request_id: int, from_emp_no: int, to_emp_no: int) -> bool:
    """
    انتقال درخواستِ بدون تصمیم از تأییدکننده‌ی فعلی (ترک‌کار / تغییر تنظیمات) به تأییدکننده‌ی جدید
    (docs/leave-requests.md «انتقال تأییدکننده»): فقط CurEmpNo و CurSection عوض می‌شود. عمداً ردیف WF_MoveUp ثبت
    نمی‌شود، چون آن ردیف یعنی «تأییدکننده‌ی قبلی تأیید کرد و ارجاع داد» و در «سوابق من» او دیده می‌شود.
    شرط WHERE (هنوز بدون تصمیم و هنوز پیش همان شخص) جلوی بازنویسی تصمیمی را که هم‌زمان گرفته شده می‌گیرد.
    خروجی: True اگر ردیف عوض شد.
    """
    cur_col = getattr(n.leave, "cur_emp_no_column", None)
    final_col = getattr(n.leave, "is_final_approved_column", None)
    if not cur_col or not final_col:
        raise RuntimeError("ستون تأییدکننده فعلی/تصمیم نهایی در نگاشت درخواست تنظیم نشده است")
    sets = [f"{quote_mssql(cur_col)} = %(to)s"]
    params = {"to": to_emp_no, "from": from_emp_no, "r": request_id}
    to_sec = get_sec_no(cur, n, to_emp_no)
    if n.has("wf_requests", "cur_section") and to_sec is not None:
        sets.append(f"{n.c('wf_requests', 'cur_section')} = %(sec)s")
        params["sec"] = to_sec
    cur.execute(
        f"UPDATE {n.requests_table} SET {', '.join(sets)} WHERE {n.requests_id} = %(r)s "
        f"AND {quote_mssql(cur_col)} = %(from)s AND {quote_mssql(final_col)} IS NULL",
        params,
    )
    return (cur.rowcount or 0) > 0


def moved_up_request_ids(cur, n: KaraNames, request_ids: list[int]) -> set[int]:
    """از میان این درخواست‌ها، آن‌هایی که ارجاع (WF_MoveUp) دارند = از مرحله‌ی سرپرست گذشته‌اند؛ بدون جدول ارجاع، خالی."""
    if not n.can_write_moveup or not request_ids:
        return set()
    found: set[int] = set()
    for i in range(0, len(request_ids), 500):
        chunk = request_ids[i : i + 500]
        placeholders = ", ".join(f"%(i{j})s" for j in range(len(chunk)))
        cur.execute(
            f"SELECT DISTINCT {n.c('wf_moveup', 'request_id')} AS RequestId FROM {quote_mssql(n.leave.wf_moveup_table_name)} "
            f"WHERE {n.c('wf_moveup', 'request_id')} IN ({placeholders})",
            {f"i{j}": rid for j, rid in enumerate(chunk)},
        )
        found |= {int(r["RequestId"]) for r in cur.fetchall()}
    return found
