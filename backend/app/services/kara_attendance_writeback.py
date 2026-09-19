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
(as_dict=True) می‌گیرند و commit را به فراخوان می‌سپارند تا هر عملیات
در یک تراکنش انجام شود.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

import jdatetime

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
    now = datetime.now()
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


def get_sec_no(cur, emp_no: int | None) -> int | None:
    if emp_no is None:
        return None
    cur.execute("SELECT TOP 1 [Sec_No] FROM [Employee] WHERE [Emp_No] = %(e)s", {"e": emp_no})
    row = cur.fetchone()
    return row["Sec_No"] if row else None


def _resolve_kara_user(cur, emp_nos: list[int | None]) -> tuple[object, str]:
    """
    کاربرِ کاراوبی که تغییر به نامش ثبت می‌شود - کاراوب کاربرِ مدیر
    تأییدکننده را می‌نویسد (UserId در Mor_Mam، Username در لاگ‌ها).
    اگر آن فرد کاربر کاراوب نداشت، کاربر درخواست‌دهنده، و در نهایت
    قدیمی‌ترین کاربر فعال (ستون‌ها NOT NULL هستند).
    """
    for emp_no in emp_nos:
        if emp_no is None:
            continue
        cur.execute(
            "SELECT TOP 1 [UserId], [Username] FROM [Users] WHERE [Emp_No] = %(e)s "
            "ORDER BY [IsActive] DESC, [CreationDate]",
            {"e": emp_no},
        )
        row = cur.fetchone()
        if row:
            return str(row["UserId"]), row["Username"]
    cur.execute("SELECT TOP 1 [UserId], [Username] FROM [Users] WHERE [IsActive] = 1 ORDER BY [CreationDate]")
    row = cur.fetchone()
    if not row:
        raise RuntimeError("هیچ کاربر فعالی در جدول Users کاراوب پیدا نشد")
    return str(row["UserId"]), row["Username"]


# ---------- ثبت درخواست ----------


def submit_extra_columns(cur, requester_emp_no: int, approver_emp_no: int | None, duration) -> dict:
    """ستون‌هایی که کاراوب هنگام ثبت پر می‌کند و پرتال قبلاً NULL می‌گذاشت."""
    return {
        "SubmittedByEmployeeID": requester_emp_no,
        "Requested_Time": str(duration),
        "DutyTools": "",
        "DutyTamin": "",
        "CurSection": get_sec_no(cur, approver_emp_no),
    }


# ---------- کسر روزانه مرخصی استحقاقی ----------


def _day_deduction_minutes(cur, emp_no: int, day: date) -> int:
    """ساعت کسر یک روز از شیفت همان روز (DailyWork -> Shifts)."""
    cur.execute(
        "SELECT TOP 1 w.[Shift_No] AS ShiftNo, s.[Kasr_Gh] AS KasrGh, s.[Kasr_Gh5] AS KasrGh5 "
        "FROM [DailyWork] w LEFT JOIN [Shifts] s ON s.[Shift_No] = w.[Shift_No] "
        "WHERE w.[Emp_No] = %(e)s AND w.[Date] = %(d)s",
        {"e": emp_no, "d": _jalali_int(day)},
    )
    row = cur.fetchone()
    thursday = day.weekday() == _THURSDAY
    if row:
        if row.get("KasrGh") is None:
            return 0  # شیفت غیرکاری (مثل جمعه/تعطیل - در Shifts تعریف نشده)
        return _hhmm_to_minutes(row["KasrGh5"] if thursday else row["KasrGh"])

    # هنوز ردیف DailyWork برای آن روز ساخته نشده (مثلاً ماه آینده):
    # آخرین شیفت کاری همین فرد + قاعده روز هفته
    if day.weekday() == _FRIDAY:
        return 0
    cur.execute(
        "SELECT TOP 1 s.[Kasr_Gh] AS KasrGh, s.[Kasr_Gh5] AS KasrGh5 "
        "FROM [DailyWork] w JOIN [Shifts] s ON s.[Shift_No] = w.[Shift_No] "
        "WHERE w.[Emp_No] = %(e)s ORDER BY w.[Date] DESC",
        {"e": emp_no},
    )
    row = cur.fetchone()
    if row and row.get("KasrGh") is not None:
        return _hhmm_to_minutes(row["KasrGh5"] if thursday else row["KasrGh"])
    return 240 if thursday else 480


def _mor_mam_amounts(cur, emp_no: int, card_no: int, start: date, end: date) -> tuple[int, int, int | None]:
    """(Requested, StandardRequested, Inc_Type) دقیقاً مطابق کاراوب."""
    if card_no in ENTITLEMENT_CARDS:
        total = 0
        day = start
        while day <= end:
            total += _day_deduction_minutes(cur, emp_no, day)
            day += timedelta(days=1)
        return -_minutes_to_hhmm(total), -total, 0
    days = (end - start).days + 1
    return days, days, None


# ---------- تأیید نهایی ----------


def apply_on_approval(cur, request: dict, approver_emp_no: int, app_id: int, branch_code: int) -> int:
    """
    اثر تأیید نهایی را مثل کاراوب اعمال می‌کند و AcceptCode نهایی را
    برمی‌گرداند (۰ یا ۸). request یک ردیف نرمال‌نشده از _select_requests_sync است.
    """
    emp_no = int(request["EmpNo"])
    card_no = int(request["CardNo"])
    user_id, username = _resolve_kara_user(cur, [approver_emp_no, emp_no])
    now, today_j, now_hhmm = _now_parts()
    start = _to_date(request["StartDate"])

    if request.get("StartHour") is not None:
        accept = _apply_hourly(cur, request, emp_no, card_no, start, user_id, username, app_id, today_j, now_hhmm)
    else:
        end = _to_date(request.get("EndDate")) or start
        _insert_mor_mam(cur, request, emp_no, card_no, start, end, user_id, username, app_id, now, today_j, branch_code)
        accept = ACCEPT_APPLIED

    cur.execute(
        "UPDATE [WF_Requests] SET [AcceptCode] = %(a)s, [CurSection] = COALESCE(%(s)s, [CurSection]) "
        "WHERE [RequestId] = %(r)s",
        {"a": accept, "s": get_sec_no(cur, approver_emp_no), "r": request["RequestId"]},
    )
    return accept


def _apply_hourly(cur, request, emp_no, card_no, day, user_id, username, app_id, today_j, now_hhmm) -> int:
    cur.execute(
        "SELECT TOP 1 [Id], [Time], [Status], [Duration], [PrevDay], [ApplicationId], [BranchCode] "
        "FROM [DataFile] WHERE [Emp_No] = %(e)s AND [Date] = %(d)s AND [Time] BETWEEN %(s)s AND %(t)s "
        "ORDER BY [Time]",
        {"e": emp_no, "d": _jalali_int(day), "s": int(request["StartHour"]), "t": int(request["EndHour"])},
    )
    punch = cur.fetchone()
    if not punch:
        return ACCEPT_APPROVED_NOT_APPLIED
    try:
        new_duration = int(request.get("Duration") or 0)
    except (TypeError, ValueError):
        new_duration = 0
    _update_punch(cur, punch, emp_no, day, card_no, new_duration, user_id, username, app_id, today_j, now_hhmm)
    return ACCEPT_APPLIED


def _update_punch(cur, punch, emp_no, day, new_status, new_duration, user_id, username, app_id, today_j, now_hhmm):
    new_app_id = (app_id << _EDITOR_SHIFT) | (int(punch["ApplicationId"]) & 0xFFFF)
    cur.execute(
        "UPDATE [DataFile] SET [Status] = %(st)s, [Duration] = %(du)s, [ApplicationId] = %(ap)s, [Checksum] = 0 "
        "WHERE [Id] = %(id)s",
        {"st": new_status, "du": new_duration, "ap": new_app_id, "id": punch["Id"]},
    )
    cur.execute(
        "INSERT INTO [LogDataFile] ([UserId], [ApplicationId], [Username], [AddictionInformation], [EditDate], "
        "[EditTime], [IoDate], [Emp_No], [OldTime], [NewTime], [OldDuration], [NewDuration], [OldStatus], "
        "[NewStatus], [OldPrevDay], [NewPrevDay], [OldVT], [NewVT], [OldAC], [NewAC], [BranchCode]) VALUES "
        "(%(u)s, %(ap)s, %(un)s, '', %(ed)s, %(et)s, %(io)s, %(e)s, %(tm)s, %(tm)s, %(od)s, %(nd)s, %(os)s, "
        "%(ns)s, %(pd)s, %(pd)s, NULL, NULL, NULL, NULL, %(b)s)",
        {
            "u": user_id,
            "ap": new_app_id,
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


def _insert_mor_mam(cur, request, emp_no, card_no, start, end, user_id, username, app_id, now, today_j, branch_code):
    requested, standard, inc_type = _mor_mam_amounts(cur, emp_no, card_no, start, end)
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
    cur.execute(
        "INSERT INTO [Mor_Mam] ([Emp_No], [S_Date], [S_DateStandard], [E_Date], [E_DateStandard], [Requested], "
        "[StandardRequested], [SerialNumber], [Issue_Date], [Type], [Babat], [Inc_Type], [UserId], "
        "[LastModifyDate], [Checksum], [BranchCode]) OUTPUT INSERTED.[RefNumber] VALUES "
        "(%(e)s, %(sd)s, %(sds)s, %(ed)s, %(eds)s, %(rq)s, %(sr)s, '', %(is)s, %(ty)s, %(bb)s, %(it)s, %(u)s, "
        "%(now)s, 0, %(b)s)",
        row,
    )
    ref_number = cur.fetchone()["RefNumber"]
    _log_mor_mam(cur, row, ref_number, change_type=1, username=username, app_id=app_id)


def _log_mor_mam(cur, row: dict, ref_number, change_type: int, username: str, app_id: int) -> None:
    cur.execute(
        "INSERT INTO [LogMorMam] ([UserId], [ApplicationId], [Username], [AdditionalInformation], [ChangeDate], "
        "[ChangeType], [RefNumber], [Emp_No], [S_Date], [S_DateStandard], [E_Date], [E_DateStandard], "
        "[Requested], [StandardRequested], [SerialNumber], [Issue_Date], [Type], [Babat], [Inc_Type], "
        "[BranchCode]) VALUES (%(u)s, %(ap)s, %(un)s, '', %(now)s, %(ct)s, %(ref)s, %(e)s, %(sd)s, %(sds)s, "
        "%(ed)s, %(eds)s, %(rq)s, %(sr)s, '', %(is)s, %(ty)s, %(bb)s, %(it)s, %(b)s)",
        {**row, "ap": app_id, "un": username, "ct": change_type, "ref": ref_number, "now": datetime.now()},
    )


# ---------- لغو اثر ----------


def revert_effects(cur, request: dict, actor_emp_no: int | None, app_id: int) -> None:
    """
    اثر یک درخواستِ تأییدشده را از کارکرد برمی‌دارد (هنگام رد، حذف یا
    ویرایش مدیریتی). اگر اثری ثبت نشده بود، کاری نمی‌کند.
    """
    emp_no = int(request["EmpNo"])
    card_no = int(request["CardNo"])
    start = _to_date(request["StartDate"])
    user_id, username = _resolve_kara_user(cur, [actor_emp_no, request.get("ApprovalByManagerEmpNo"), emp_no])
    now, today_j, now_hhmm = _now_parts()

    if request.get("StartHour") is not None:
        cur.execute("SELECT [AcceptCode] FROM [WF_Requests] WHERE [RequestId] = %(r)s", {"r": request["RequestId"]})
        state = cur.fetchone()
        if not state or state.get("AcceptCode") != ACCEPT_APPLIED:
            return  # روی ترددی اعمال نشده بود
        cur.execute(
            "SELECT TOP 1 [Id], [Time], [Status], [Duration], [PrevDay], [ApplicationId], [BranchCode] "
            "FROM [DataFile] WHERE [Emp_No] = %(e)s AND [Date] = %(d)s AND [Time] BETWEEN %(s)s AND %(t)s "
            "AND [Status] = %(c)s ORDER BY [Time]",
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
            _update_punch(cur, punch, emp_no, start, 0, 0, user_id, username, app_id, today_j, now_hhmm)
        return

    end = _to_date(request.get("EndDate")) or start
    cur.execute(
        "SELECT TOP 1 * FROM [Mor_Mam] WHERE [Emp_No] = %(e)s AND [S_Date] = %(sd)s AND "
        "ISNULL([E_Date], [S_Date]) = %(ed)s AND [Type] = %(ty)s "
        "ORDER BY CASE WHEN [Babat] = %(bb)s THEN 0 ELSE 1 END, [RefNumber] DESC",
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
    cur.execute("DELETE FROM [Mor_Mam] WHERE [RefNumber] = %(r)s", {"r": mor["RefNumber"]})
    log_row = {
        "u": user_id,
        "e": mor["Emp_No"],
        "sd": mor["S_Date"],
        "sds": mor["S_DateStandard"],
        "ed": mor["E_Date"],
        "eds": mor["E_DateStandard"],
        "rq": mor["Requested"],
        "sr": mor["StandardRequested"],
        "is": mor["Issue_Date"],
        "ty": mor["Type"],
        "bb": mor["Babat"],
        "it": mor["Inc_Type"],
        "b": mor["BranchCode"],
    }
    _log_mor_mam(cur, log_row, mor["RefNumber"], change_type=3, username=username, app_id=app_id)


def clear_accept_code(cur, request_id: int) -> None:
    cur.execute("UPDATE [WF_Requests] SET [AcceptCode] = NULL WHERE [RequestId] = %(r)s", {"r": request_id})


def delete_request_state_rows(cur, request_id: int) -> None:
    """WF_RequestState به WF_Requests کلید خارجی ندارد - باید دستی پاک شود."""
    cur.execute("DELETE FROM [WF_RequestState] WHERE [RequestId] = %(r)s", {"r": request_id})
