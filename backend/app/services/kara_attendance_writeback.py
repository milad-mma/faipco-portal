"""
هم‌رفتاری کامل با کاراوب هنگام ثبت/تأیید/لغو درخواست مرخصی و ماموریت.

همه چیز این فایل با آزمایش مستقیم روی دیتابیس واقعی کاراوب (۱۴۰۵/۰۶/۲۸،
درخواست‌های ۲۲، ۲۶، ۴۳ تا ۴۹) استخراج شده - نه حدس:

ثبت درخواست (کاراوب):
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
        دیگری تغییر نمی‌کند. کاراوب در این حالت فقط یک هشدار نمایش می‌دهد
        که طبق خواست کاربر، پرتال نمایش نمی‌دهد.

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

Checksum: مقدار آن را برنامه کاراوب محاسبه می‌کند و الگوریتمش در دسترس
نیست؛ ۰ نوشته می‌شود (بخش بزرگی از ردیف‌های موجود Mor_Mam/DataFile هم ۰
دارند و کاراوب با آن‌ها مشکلی ندارد).

⚠️ فقط برای SQL Server (کاراوب). همه توابع یک cursor از pymssql
(as_dict=True) و یک KaraNames (نام جدول/ستون‌ها از تنظیمات سایت) می‌گیرند
و commit را به فراخوان می‌سپارند تا هر عملیات در یک تراکنش انجام شود.
هیچ نام جدول/ستونی در این فایل مستقیم نوشته نشده (app/services/kara_schema.py).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import jdatetime

from app.services.kara_schema import KaraNames

_KARA_TZ = ZoneInfo("Asia/Tehran")


def kara_now() -> datetime:
    """
    ساعت محلی ایران (بدون tzinfo) - کاراوب همه تاریخ/ساعت‌ها را به وقت
    محلی می‌نویسد؛ سرور پرتال UTC است و datetime.now() خام، ۳:۳۰ ساعت
    عقب ثبت می‌کرد (تأییدِ ۱۲:۳۵ به‌صورت ۰۹:۰۵ ثبت شد).
    """
    return datetime.now(_KARA_TZ).replace(tzinfo=None)

ACCEPT_APPLIED = 0
ACCEPT_APPROVED_NOT_APPLIED = 8
ACCEPT_CANCELLED = 22

# کارت‌هایی که از مانده مرخصی (ساعتی) کسر می‌شوند - با داده واقعی فقط ۵۷
ENTITLEMENT_CARDS = {57}

# پرچم «ویرایش‌شده توسط برنامه X» روی ApplicationId تردد = شناسه برنامه << 16
# (۶۵۵۳۶ = دسکتاپ کاراوب، ۲۶۲۱۴۴ = وب کاراوب)
_EDITOR_SHIFT = 16

_THURSDAY = 3  # date.weekday()
_FRIDAY = 4


# ---------- کمکی‌ها ----------


def _jalali_int(d: date) -> int:
    j = jdatetime.date.fromgregorian(date=d)
    return j.year * 10000 + j.month * 100 + j.day


def _now_parts() -> tuple[datetime, int, int]:
    now = kara_now()
    return now, _jalali_int(now.date()), now.hour * 100 + now.minute


def _to_date(value) -> date | None:
    if value is None:
        return None
    return value.date() if hasattr(value, "date") else value


def _hhmm_to_minutes(value: int) -> int:
    value = int(value or 0)
    return (value // 100) * 60 + value % 100


def _minutes_to_hhmm(minutes: int) -> int:
    return (minutes // 60) * 100 + minutes % 60


def get_sec_no(cur, n: KaraNames, emp_no: int | None) -> int | None:
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
    کاربرِ کاراوبی که تغییر به نامش ثبت می‌شود - کاراوب کاربرِ مدیر
    تأییدکننده را می‌نویسد (UserId در Mor_Mam، Username در لاگ‌ها).
    اگر آن فرد کاربر کاراوب نداشت، کاربر درخواست‌دهنده، و در نهایت
    قدیمی‌ترین کاربر فعال (ستون‌ها NOT NULL هستند).
    """
    select = (
        f"SELECT TOP 1 {n.c('users', 'user_id')} AS UserId, {n.c('users', 'username')} AS Username "
        f"FROM {n.t('users')} "
    )
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
    cur.execute(select + f"WHERE {n.c('users', 'is_active')} = 1 ORDER BY {n.c('users', 'creation_date')}")
    row = cur.fetchone()
    if not row:
        raise RuntimeError("هیچ کاربر فعالی در جدول کاربران کاراوب پیدا نشد")
    return str(row["UserId"]), row["Username"]


# ---------- ثبت درخواست ----------


def submit_extra_columns(cur, n: KaraNames, requester_emp_no: int, approver_emp_no: int | None, duration) -> dict:
    """
    ستون‌هایی که کاراوب هنگام ثبت پر می‌کند - فقط آن‌هایی که در تنظیمات
    نگاشت شده‌اند (ستون نگاشت‌نشده نوشته نمی‌شود).
    """
    values = {
        "submitted_by": requester_emp_no,
        "requested_time": str(duration),
        "duty_tools": "",
        "duty_tamin": "",
    }
    columns = {n.raw("wf_requests", role): value for role, value in values.items() if n.has("wf_requests", role)}
    if n.has("wf_requests", "cur_section"):
        columns[n.raw("wf_requests", "cur_section")] = get_sec_no(cur, n, approver_emp_no)
    return columns


# ---------- کسر روزانه مرخصی استحقاقی ----------


def _kasr_minutes(row: dict | None, thursday: bool) -> int | None:
    """None یعنی «از این منبع اطلاعاتی نیامد»؛ ۰ یعنی روز غیرکاری."""
    if not row or row.get("ShiftNo") is None:
        return None
    if row.get("KasrGh") is None:
        return 0  # شیفت غیرکاری/تعطیل (در جدول شیفت‌ها تعریف نشده، مثل ۵۰۱)
    return _hhmm_to_minutes(row["KasrGh5"] if thursday else row["KasrGh"])


def _day_deduction_minutes(cur, n: KaraNames, emp_no: int, day: date) -> int:
    """
    ساعت کسر یک روز: شیفت همان روز -> ستون کسر مرخصی استحقاقی آن شیفت.
    هر منبع فقط اگر نگاشت شده باشد استفاده می‌شود؛ در نهایت قاعده روز هفته.
    """
    thursday = day.weekday() == _THURSDAY
    jalali = _jalali_int(day)

    if n.has("shifts"):
        shifts, sh_no = n.t("shifts"), n.c("shifts", "shift_no")
        kasr = f"s.{n.c('shifts', 'kasr_gh')} AS KasrGh, s.{n.c('shifts', 'kasr_gh5')} AS KasrGh5"

        # ۱) کارکرد روزانه کاراوب (فقط شماره شیفت روز خوانده می‌شود)
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

        # ۲) کارکرد روزانه فقط تا آخر ماه جاری ساخته می‌شود - برای ماه‌های
        # آینده، تقویم شیفت گروهی کاراوب (جمعه‌ها و تعطیلات رسمی = غیرکاری):
        # گروه فرد در آن تاریخ -> شیفت آن روز گروه. (با شهریور ۱۴۰۵ مقایسه
        # شد: ۷۶۰۹ از ۷۶۲۳ روز با کارکرد روزانه یکی بود)
        if n.has("grp_shift") and n.has("emp_grps"):
            j_year, j_month, j_day = jalali // 10000, (jalali // 100) % 100, jalali % 100
            day_col = f"[{n.raw('grp_shift', 'day_prefix')}{j_day}]"
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

    # ۳) آخرین راه: قاعده روز هفته
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
    return 240 if thursday else 480


def _mor_mam_amounts(cur, n: KaraNames, emp_no: int, card_no: int, start: date, end: date):
    """(Requested, StandardRequested, Inc_Type) دقیقاً مطابق کاراوب."""
    if card_no in ENTITLEMENT_CARDS:
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
    """فقط ستون‌هایی که نگاشت شده‌اند به‌روز می‌شوند."""
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


def apply_on_approval(cur, n: KaraNames, request: dict, approver_emp_no: int, app_id: int, branch_code: int) -> int:
    """
    اثر تأیید نهایی را مثل کاراوب اعمال می‌کند و AcceptCode نهایی را
    برمی‌گرداند (۰ یا ۸). request یک ردیف نرمال‌نشده از _select_requests_sync است.
    """
    emp_no = int(request["EmpNo"])
    card_no = int(request["CardNo"])
    hourly = request.get("StartHour") is not None
    # ⚠️ قابلیتی که جدول‌هایش نگاشت نشده، اصلاً اجرا نمی‌شود (بدون تیک جداگانه)
    if (hourly and not n.can_write_hourly) or (not hourly and not n.can_write_daily):
        return None
    user_id, username = _resolve_kara_user(cur, n, [approver_emp_no, emp_no])
    now, today_j, now_hhmm = _now_parts()
    start = _to_date(request["StartDate"])

    if hourly:
        accept = _apply_hourly(cur, n, request, emp_no, card_no, start, user_id, username, app_id, today_j, now_hhmm)
    else:
        end = _to_date(request.get("EndDate")) or start
        _insert_mor_mam(
            cur, n, request, emp_no, card_no, start, end, user_id, username, app_id, now, today_j, branch_code
        )
        accept = ACCEPT_APPLIED

    _set_accept_code(cur, n, request["RequestId"], accept, get_sec_no(cur, n, approver_emp_no))
    return accept


def _punch_select(n: KaraNames) -> str:
    return (
        f"SELECT TOP 1 {n.c('datafile', 'id')} AS Id, {n.df_time} AS Time, "
        f"{n.c('datafile', 'status')} AS Status, {n.c('datafile', 'duration')} AS Duration, "
        f"{n.c('datafile', 'prev_day')} AS PrevDay, {n.c('datafile', 'application_id')} AS ApplicationId, "
        f"{n.c('datafile', 'branch_code')} AS BranchCode FROM {n.df_table} "
        f"WHERE {n.df_emp_no} = %(e)s AND {n.df_date} = %(d)s "
        f"AND {n.df_time} BETWEEN %(s)s AND %(t)s "
    )


def _apply_hourly(cur, n, request, emp_no, card_no, day, user_id, username, app_id, today_j, now_hhmm) -> int:
    cur.execute(
        _punch_select(n) + f"ORDER BY {n.df_time}",
        {"e": emp_no, "d": _jalali_int(day), "s": int(request["StartHour"]), "t": int(request["EndHour"])},
    )
    punch = cur.fetchone()
    if not punch:
        return ACCEPT_APPROVED_NOT_APPLIED
    try:
        new_duration = int(request.get("Duration") or 0)
    except (TypeError, ValueError):
        new_duration = 0
    _update_punch(cur, n, punch, emp_no, day, card_no, new_duration, user_id, username, app_id, today_j, now_hhmm)
    return ACCEPT_APPLIED


def _update_punch(
    cur, n, punch, emp_no, day, new_status, new_duration, user_id, username, app_id, today_j, now_hhmm, restore=False
):
    source_app_id = int(punch["ApplicationId"]) & 0xFFFF
    # ردیف لاگ همیشه با پرچم «گردش کار» ثبت می‌شود (مثل کاراوب)
    log_app_id = (app_id << _EDITOR_SHIFT) | source_app_id
    # ⚠️ طبق گزارش کاربر: بعد از لغو اثر (حذف/رد درخواست)، پرچم «گردش کار»
    # روی خودِ تردد باقی می‌ماند و در کاراوب با Hover «گردش کار» نشان داده
    # می‌شد. هنگام لغو، ApplicationId تردد به منبع اولیه‌اش برمی‌گردد تا
    # تردد دقیقاً مثل قبل از اعمال درخواست شود.
    punch_app_id = source_app_id if restore else log_app_id
    cur.execute(
        f"UPDATE {n.df_table} SET {n.c('datafile', 'status')} = %(st)s, {n.c('datafile', 'duration')} = %(du)s, "
        f"{n.c('datafile', 'application_id')} = %(ap)s, {n.c('datafile', 'checksum')} = 0 "
        f"WHERE {n.c('datafile', 'id')} = %(id)s",
        {"st": new_status, "du": new_duration, "ap": punch_app_id, "id": punch["Id"]},
    )
    if not n.has("log_datafile"):
        return  # لاگ تغییر تردد نگاشت نشده
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
    requested, standard, inc_type = _mor_mam_amounts(cur, n, emp_no, card_no, start, end)
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
    ref_number = cur.fetchone()["RefNumber"]
    _log_mor_mam(cur, n, row, ref_number, change_type=1, username=username, app_id=app_id)


def _log_mor_mam(cur, n: KaraNames, row: dict, ref_number, change_type: int, username: str, app_id: int) -> None:
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


def revert_effects(cur, n: KaraNames, request: dict, actor_emp_no: int | None, app_id: int) -> None:
    """
    اثر یک درخواستِ تأییدشده را از کارکرد برمی‌دارد (هنگام رد، حذف یا
    ویرایش مدیریتی). اگر اثری ثبت نشده بود، کاری نمی‌کند.
    """
    emp_no = int(request["EmpNo"])
    card_no = int(request["CardNo"])
    start = _to_date(request["StartDate"])
    hourly = request.get("StartHour") is not None
    if (hourly and not n.can_write_hourly) or (not hourly and not n.can_write_daily):
        return
    user_id, username = _resolve_kara_user(cur, n, [actor_emp_no, request.get("ApprovalByManagerEmpNo"), emp_no])
    now, today_j, now_hhmm = _now_parts()

    if hourly:
        if n.has("wf_requests", "accept_code"):
            cur.execute(
                f"SELECT {n.c('wf_requests', 'accept_code')} AS AcceptCode FROM {n.requests_table} "
                f"WHERE {n.requests_id} = %(r)s",
                {"r": request["RequestId"]},
            )
            state = cur.fetchone()
            if not state or state.get("AcceptCode") != ACCEPT_APPLIED:
                return  # روی ترددی اعمال نشده بود
        cur.execute(
            _punch_select(n) + f"AND {n.c('datafile', 'status')} = %(c)s ORDER BY {n.df_time}",
            {
                "e": emp_no,
                "d": _jalali_int(start),
                "s": int(request["StartHour"]),
                "t": int(request["EndHour"]),
                "c": card_no,
            },
        )
        punch = cur.fetchone()
        if punch:
            # ⚠️ وضعیت/مدتِ قبل از اعمال از آخرین لاگ همین پرتال خوانده می‌شود -
            # اگر تردد از اول با کارت ماموریت/مرخصی زده شده بود (Status=۹/۱۷
            # از خودِ دستگاه)، حذف درخواست نباید آن علامت واقعی را هم پاک کند.
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
                        "d": _jalali_int(start),
                        "t": punch["Time"],
                        "c": card_no,
                        "flag": app_id << _EDITOR_SHIFT,
                    },
                )
                before = cur.fetchone() or {}
            _update_punch(
                cur, n, punch, emp_no, start, before.get("OldStatus") or 0, before.get("OldDuration") or 0,
                user_id, username, app_id, today_j, now_hhmm, restore=True,
            )
        return

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
    if not n.has("wf_requests", "accept_code"):
        return
    accept_col = n.c("wf_requests", "accept_code")
    cur.execute(f"UPDATE {n.requests_table} SET {accept_col} = NULL WHERE {n.requests_id} = %(r)s", {"r": request_id})


def delete_request_state_rows(cur, n: KaraNames, request_id: int) -> None:
    """جدول وضعیت درخواست (WF_RequestState) به جدول درخواست کلید خارجی ندارد - باید دستی پاک شود."""
    if not n.has("wf_request_state"):
        return
    cur.execute(
        f"DELETE FROM {n.t('wf_request_state')} WHERE {n.c('wf_request_state', 'request_id')} = %(r)s",
        {"r": request_id},
    )


# ---------- تردد فراموش‌شده ----------
#
# رفتار کاراوب (تأییدشده با درخواست‌های ۵۶ و ۵۷، ۱۴۰۵/۰۶/۲۸):
#   ثبت: یک ردیف درخواست به‌ازای هر تردد - StartDate = تاریخ تردد،
#        StartHour = ساعت تردد، EndHour = ۰، EndDate = NULL، Duration = '0'
#   تأیید نهایی: یک ردیف تازه در جدول تردد (Status 0، Modify 1، Direction 0،
#        ApplicationId = شناسه برنامه، DeviceNumber NULL، Duration 0،
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
    """تأیید نهایی تردد فراموش‌شده: درج تردد + لاگ + AcceptCode = ۰."""
    if not n.can_write_punch:
        raise RuntimeError("ستون‌های لازم جدول تردد برای ثبت تردد فراموش‌شده در تنظیمات سایت نگاشت نشده‌اند")
    emp_no = int(request["EmpNo"])
    day = _to_date(request["StartDate"])
    date_int = _jalali_int(day)
    time_int = int(request["StartHour"])
    user_id, username = _resolve_kara_user(cur, n, [approver_emp_no, emp_no])
    _, today_j, now_hhmm = _now_parts()

    if not punch_exists(cur, n, emp_no, date_int, time_int):
        D = lambda role: n.c("datafile", role)  # noqa: E731
        cur.execute(
            f"INSERT INTO {n.df_table} ({n.df_emp_no}, {n.df_date}, {n.df_time}, {D('status')}, {D('modify')}, "
            f"{D('direction')}, {D('application_id')}, {D('duration')}, {D('prev_day')}, {D('vt')}, {D('ac')}, "
            f"{D('checksum')}, {D('branch_code')}) VALUES "
            "(%(e)s, %(d)s, %(t)s, 0, 1, 0, %(ap)s, 0, 0, 0, 0, 0, %(b)s)",
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
    لغو اثر تردد فراموش‌شده (حذف/رد مدیریتی پس از تأیید): فقط همان ترددی
    که این پرتال/گردش کار درج کرده بود حذف می‌شود - تردد دستگاه یا تردد
    دستیِ کاراوب هرگز پاک نمی‌شود.
    """
    if not n.can_write_punch:
        return
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
    user_id, username = _resolve_kara_user(cur, n, [actor_emp_no, request.get("ApprovalByManagerEmpNo"), emp_no])
    _, today_j, now_hhmm = _now_parts()
    cur.execute(f"DELETE FROM {n.df_table} WHERE {D('id')} = %(id)s", {"id": punch["Id"]})
    log_app_id = (app_id << _EDITOR_SHIFT) | (int(punch["ApplicationId"]) & 0xFFFF)
    _log_punch_change(
        cur, n, user_id, username, log_app_id, today_j, now_hhmm, date_int, emp_no, punch["BranchCode"],
        old=punch, new=None,
    )


def _log_punch_change(cur, n, user_id, username, app_id, today_j, now_hhmm, io_date, emp_no, branch_code, old, new):
    """ردیف لاگ درج (old=None) یا حذف (new=None) تردد - دقیقاً مثل کاراوب."""
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
    ارجاع درخواست از سرپرست به مسئول نیروی انسانی: تأییدکننده فعلی و
    واحد او عوض می‌شود و (اگر نگاشت شده باشد) یک ردیف در جدول ارجاع
    کاراوب ثبت می‌شود تا تاریخچه مسیر درخواست در خودِ کاراوب هم دیده شود.
    """
    cur_col = getattr(n.leave, "cur_emp_no_column", None)
    if not cur_col:
        raise RuntimeError("ستون تأییدکننده فعلی در نگاشت درخواست تنظیم نشده است")
    sets, params = [f"[{cur_col}] = %(to)s"], {"to": to_emp_no, "r": request["RequestId"]}
    from_sec = get_sec_no(cur, n, from_emp_no)
    to_sec = get_sec_no(cur, n, to_emp_no)
    if n.has("wf_requests", "cur_section") and to_sec is not None:
        sets.append(f"{n.c('wf_requests', 'cur_section')} = %(sec)s")
        params["sec"] = to_sec
    cur.execute(f"UPDATE {n.requests_table} SET {', '.join(sets)} WHERE {n.requests_id} = %(r)s", params)

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
        f"INSERT INTO [{n.leave.wf_moveup_table_name}] ({', '.join(c for c, _ in columns)}) "
        f"VALUES ({', '.join(f'%(v{i})s' for i in range(len(columns)))})",
        {f"v{i}": value for i, (_, value) in enumerate(columns)},
    )


def request_ids_moved_by(cur, n: KaraNames, from_emp_no: int) -> list[int]:
    """شناسه درخواست‌هایی که این فرد (به‌عنوان سرپرست) به مرحله بعد ارجاع داده است."""
    if not n.can_write_moveup:
        return []
    cur.execute(
        f"SELECT DISTINCT {n.c('wf_moveup', 'request_id')} AS RequestId FROM [{n.leave.wf_moveup_table_name}] "
        f"WHERE {n.c('wf_moveup', 'from_manager')} = %(e)s",
        {"e": from_emp_no},
    )
    return [int(r["RequestId"]) for r in cur.fetchall()]
