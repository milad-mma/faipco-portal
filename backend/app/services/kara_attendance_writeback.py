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
    if emp_no is None:
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
    """ستون‌هایی که کاراوب هنگام ثبت پر می‌کند و پرتال قبلاً NULL می‌گذاشت (نام ستون‌ها از تنظیمات)."""
    return {
        n.raw("wf_requests", "submitted_by"): requester_emp_no,
        n.raw("wf_requests", "requested_time"): str(duration),
        n.raw("wf_requests", "duty_tools"): "",
        n.raw("wf_requests", "duty_tamin"): "",
        n.raw("wf_requests", "cur_section"): get_sec_no(cur, n, approver_emp_no),
    }


# ---------- کسر روزانه مرخصی استحقاقی ----------


def _kasr_minutes(row: dict | None, thursday: bool) -> int | None:
    """None یعنی «از این منبع اطلاعاتی نیامد»؛ ۰ یعنی روز غیرکاری."""
    if not row or row.get("ShiftNo") is None:
        return None
    if row.get("KasrGh") is None:
        return 0  # شیفت غیرکاری/تعطیل (در جدول شیفت‌ها تعریف نشده، مثل ۵۰۱)
    return _hhmm_to_minutes(row["KasrGh5"] if thursday else row["KasrGh"])


def _day_deduction_minutes(cur, n: KaraNames, emp_no: int, day: date) -> int:
    """ساعت کسر یک روز: شیفت همان روز -> ستون کسر مرخصی استحقاقی آن شیفت."""
    thursday = day.weekday() == _THURSDAY
    jalali = _jalali_int(day)
    shifts, sh_no = n.t("shifts"), n.c("shifts", "shift_no")
    kasr = f"s.{n.c('shifts', 'kasr_gh')} AS KasrGh, s.{n.c('shifts', 'kasr_gh5')} AS KasrGh5"

    # ۱) کارکرد روزانه کاراوب (فقط شماره شیفت روز خوانده می‌شود)
    cur.execute(
        f"SELECT TOP 1 w.{n.c('daily_work', 'shift_no')} AS ShiftNo, {kasr} "
        f"FROM {n.t('daily_work')} w LEFT JOIN {shifts} s ON s.{sh_no} = w.{n.c('daily_work', 'shift_no')} "
        f"WHERE w.{n.c('daily_work', 'emp_no')} = %(e)s AND w.{n.c('daily_work', 'date')} = %(d)s",
        {"e": emp_no, "d": jalali},
    )
    minutes = _kasr_minutes(cur.fetchone(), thursday)
    if minutes is not None:
        return minutes

    # ۲) کارکرد روزانه فقط تا آخر ماه جاری ساخته می‌شود - برای ماه‌های
    # آینده، تقویم شیفت گروهی کاراوب (جمعه‌ها و تعطیلات رسمی = غیرکاری):
    # گروه فرد در آن تاریخ -> شیفت آن روز گروه. (با شهریور ۱۴۰۵ مقایسه
    # شد: ۷۶۰۹ از ۷۶۲۳ روز با کارکرد روزانه یکی بود)
    j_year, j_month, j_day = jalali // 10000, (jalali // 100) % 100, jalali % 100
    day_col = f"[{n.raw('grp_shift', 'day_prefix')}{j_day}]"
    cur.execute(
        f"SELECT TOP 1 g.{day_col} AS ShiftNo, {kasr} "
        f"FROM {n.t('grp_shift')} g LEFT JOIN {shifts} s ON s.{sh_no} = g.{day_col} "
        f"WHERE g.{n.c('grp_shift', 'year')} = %(y)s AND g.{n.c('grp_shift', 'month')} = %(m)s "
        f"AND g.{n.c('grp_shift', 'grp_no')} = ("
        f"SELECT TOP 1 e.{n.c('emp_grps', 'new_grp_no')} FROM {n.t('emp_grps')} e "
        f"WHERE e.{n.c('emp_grps', 'emp_no')} = %(e)s AND e.{n.c('emp_grps', 'date')} <= %(d)s "
        f"ORDER BY e.{n.c('emp_grps', 'date')} DESC)",
        {"y": j_year, "m": j_month, "e": emp_no, "d": jalali},
    )
    minutes = _kasr_minutes(cur.fetchone(), thursday)
    if minutes is not None:
        return minutes

    # ۳) آخرین راه: قاعده روز هفته با آخرین شیفت کاری همین فرد
    if day.weekday() == _FRIDAY:
        return 0
    cur.execute(
        f"SELECT TOP 1 w.{n.c('daily_work', 'shift_no')} AS ShiftNo, {kasr} "
        f"FROM {n.t('daily_work')} w JOIN {shifts} s ON s.{sh_no} = w.{n.c('daily_work', 'shift_no')} "
        f"WHERE w.{n.c('daily_work', 'emp_no')} = %(e)s ORDER BY w.{n.c('daily_work', 'date')} DESC",
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
    accept_col, section_col = n.c("wf_requests", "accept_code"), n.c("wf_requests", "cur_section")
    cur.execute(
        f"UPDATE {n.requests_table} SET {accept_col} = %(a)s, {section_col} = COALESCE(%(s)s, {section_col}) "
        f"WHERE {n.requests_id} = %(r)s",
        {"a": accept, "s": cur_section, "r": request_id},
    )


def apply_on_approval(cur, n: KaraNames, request: dict, approver_emp_no: int, app_id: int, branch_code: int) -> int:
    """
    اثر تأیید نهایی را مثل کاراوب اعمال می‌کند و AcceptCode نهایی را
    برمی‌گرداند (۰ یا ۸). request یک ردیف نرمال‌نشده از _select_requests_sync است.
    """
    emp_no = int(request["EmpNo"])
    card_no = int(request["CardNo"])
    user_id, username = _resolve_kara_user(cur, n, [approver_emp_no, emp_no])
    now, today_j, now_hhmm = _now_parts()
    start = _to_date(request["StartDate"])

    if request.get("StartHour") is not None:
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
        f"SELECT TOP 1 {n.c('datafile', 'id')} AS Id, {n.c('datafile', 'time')} AS Time, "
        f"{n.c('datafile', 'status')} AS Status, {n.c('datafile', 'duration')} AS Duration, "
        f"{n.c('datafile', 'prev_day')} AS PrevDay, {n.c('datafile', 'application_id')} AS ApplicationId, "
        f"{n.c('datafile', 'branch_code')} AS BranchCode FROM {n.t('datafile')} "
        f"WHERE {n.c('datafile', 'emp_no')} = %(e)s AND {n.c('datafile', 'date')} = %(d)s "
        f"AND {n.c('datafile', 'time')} BETWEEN %(s)s AND %(t)s "
    )


def _apply_hourly(cur, n, request, emp_no, card_no, day, user_id, username, app_id, today_j, now_hhmm) -> int:
    cur.execute(
        _punch_select(n) + f"ORDER BY {n.c('datafile', 'time')}",
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
        f"UPDATE {n.t('datafile')} SET {n.c('datafile', 'status')} = %(st)s, {n.c('datafile', 'duration')} = %(du)s, "
        f"{n.c('datafile', 'application_id')} = %(ap)s, {n.c('datafile', 'checksum')} = 0 "
        f"WHERE {n.c('datafile', 'id')} = %(id)s",
        {"st": new_status, "du": new_duration, "ap": punch_app_id, "id": punch["Id"]},
    )
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
    user_id, username = _resolve_kara_user(cur, n, [actor_emp_no, request.get("ApprovalByManagerEmpNo"), emp_no])
    now, today_j, now_hhmm = _now_parts()

    if request.get("StartHour") is not None:
        cur.execute(
            f"SELECT {n.c('wf_requests', 'accept_code')} AS AcceptCode FROM {n.requests_table} "
            f"WHERE {n.requests_id} = %(r)s",
            {"r": request["RequestId"]},
        )
        state = cur.fetchone()
        if not state or state.get("AcceptCode") != ACCEPT_APPLIED:
            return  # روی ترددی اعمال نشده بود
        cur.execute(
            _punch_select(n) + f"AND {n.c('datafile', 'status')} = %(c)s ORDER BY {n.c('datafile', 'time')}",
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
    accept_col = n.c("wf_requests", "accept_code")
    cur.execute(f"UPDATE {n.requests_table} SET {accept_col} = NULL WHERE {n.requests_id} = %(r)s", {"r": request_id})


def delete_request_state_rows(cur, n: KaraNames, request_id: int) -> None:
    """جدول وضعیت درخواست (WF_RequestState) به جدول درخواست کلید خارجی ندارد - باید دستی پاک شود."""
    cur.execute(
        f"DELETE FROM {n.t('wf_request_state')} WHERE {n.c('wf_request_state', 'request_id')} = %(r)s",
        {"r": request_id},
    )
