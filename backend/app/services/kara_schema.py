"""
نگاشت نام جدول/ستون‌های کاراوب برای «ثبت مرخصی/ماموریت در کارکرد» و
«نمایش مرخصی/ماموریت در گزارش تردد».

⚠️ طبق درخواست صریح کاربر:
  - هیچ نام جدول/ستونی مستقیم در کد نیست - همه از تنظیمات سایت می‌آیند.
  - هیچ تیک «فعال/غیرفعال» جداگانه‌ای وجود ندارد: هر قابلیت فقط وقتی کار
    می‌کند که جدول‌های لازمش نگاشت شده باشند (مثل بقیه نگاشت‌های پروژه).
  - چیزی دوبار نگاشت نمی‌شود: جدول/ستون‌های اصلی تردد (جدول، کد پرسنلی،
    تاریخ، ساعت) همان‌هایی هستند که در تب «نگاشت تردد» تعریف شده‌اند.

محل نگهداری:
  - AttendanceMapping.kara_schema  (تب «نگاشت تردد»): ستون‌های تکمیلی جدول
    تردد، لاگ تغییر تردد، کارکرد روزانه، شیفت‌ها، تقویم شیفت گروهی، گروه پرسنل
  - LeaveRequestMapping.kara_schema (تب «مرخصی/ماموریت»): ستون‌های تکمیلی
    جدول درخواست، جدول‌های وابسته، کاربران، مرخصی/ماموریت روزانه و لاگ آن،
    ستون‌های تکمیلی جدول کارت‌ها

مقادیر «پیش‌فرض» فقط برای دکمه «پر کردن با نام‌های کاراوب» در پنل هستند -
تا ادمین ذخیره نکند، هیچ‌کدام استفاده نمی‌شوند.

کلیدها «گروه.نقش» هستند؛ «گروه.table» نام جدول است. در گروه‌های جدول‌دار،
اگر نام جدول خالی باشد آن گروه غیرفعال است و اگر پر باشد همه ستون‌هایش
الزامی‌اند. گروه‌های «فقط ستون» (ستون‌های تکمیلی یک جدولِ از قبل نگاشت‌شده)
هر ستونشان جداگانه اختیاری است.
"""
from __future__ import annotations

import re

LEAVE_SCHEMA_DEFAULTS: dict[str, str] = {
    # ستون‌های تکمیلی جدول درخواست (نام جدول/شناسه در بالای همین تب است)
    "wf_requests.submitted_by": "SubmittedByEmployeeID",
    "wf_requests.requested_time": "Requested_Time",
    "wf_requests.accept_code": "AcceptCode",
    "wf_requests.cur_section": "CurSection",
    "wf_requests.duty_tools": "DutyTools",
    "wf_requests.duty_tamin": "DutyTamin",
    # ستون‌های جدول‌های وابسته (نام جدول‌ها در بخش WF_Reviews همین تب است)
    "wf_reviews.id": "Id",
    "wf_attachment.request_id": "RequestId",
    "wf_moveup.request_id": "RequestId",
    # ارجاع درخواست تردد فراموش‌شده از سرپرست به مسئول نیروی انسانی
    "wf_moveup.date": "DateMoveUp",
    "wf_moveup.from_manager": "FromManagerEmp_No",
    "wf_moveup.to_manager": "ToManagerEmp_No",
    "wf_moveup.card_no": "CardNo",
    "wf_moveup.from_sec": "FromSec_No",
    "wf_moveup.to_sec": "ToSec_No",
    "wf_parallel.request_id": "RequestId",
    "wf_request_state.table": "WF_RequestState",
    "wf_request_state.request_id": "RequestId",
    # کاربران کاراوب (ثبت‌کننده تغییر)
    "users.table": "Users",
    "users.user_id": "UserId",
    "users.username": "Username",
    "users.emp_no": "Emp_No",
    "users.is_active": "IsActive",
    "users.creation_date": "CreationDate",
    # مرخصی/ماموریت روزانه
    "mor_mam.table": "Mor_Mam",
    "mor_mam.ref_number": "RefNumber",
    "mor_mam.emp_no": "Emp_No",
    "mor_mam.s_date": "S_Date",
    "mor_mam.s_date_standard": "S_DateStandard",
    "mor_mam.e_date": "E_Date",
    "mor_mam.e_date_standard": "E_DateStandard",
    "mor_mam.requested": "Requested",
    "mor_mam.standard_requested": "StandardRequested",
    "mor_mam.serial_number": "SerialNumber",
    "mor_mam.issue_date": "Issue_Date",
    "mor_mam.type": "Type",
    "mor_mam.babat": "Babat",
    "mor_mam.inc_type": "Inc_Type",
    "mor_mam.user_id": "UserId",
    "mor_mam.last_modify_date": "LastModifyDate",
    "mor_mam.checksum": "Checksum",
    "mor_mam.branch_code": "BranchCode",
    # لاگ مرخصی/ماموریت روزانه
    "log_mor_mam.table": "LogMorMam",
    "log_mor_mam.user_id": "UserId",
    "log_mor_mam.application_id": "ApplicationId",
    "log_mor_mam.username": "Username",
    "log_mor_mam.additional_info": "AdditionalInformation",
    "log_mor_mam.change_date": "ChangeDate",
    "log_mor_mam.change_type": "ChangeType",
    "log_mor_mam.ref_number": "RefNumber",
    "log_mor_mam.emp_no": "Emp_No",
    "log_mor_mam.s_date": "S_Date",
    "log_mor_mam.s_date_standard": "S_DateStandard",
    "log_mor_mam.e_date": "E_Date",
    "log_mor_mam.e_date_standard": "E_DateStandard",
    "log_mor_mam.requested": "Requested",
    "log_mor_mam.standard_requested": "StandardRequested",
    "log_mor_mam.serial_number": "SerialNumber",
    "log_mor_mam.issue_date": "Issue_Date",
    "log_mor_mam.type": "Type",
    "log_mor_mam.babat": "Babat",
    "log_mor_mam.inc_type": "Inc_Type",
    "log_mor_mam.branch_code": "BranchCode",
    # ستون‌های تکمیلی جدول کارت‌ها (جدول/شماره/عنوان در بخش Cards همین تب است)
    "cards.card_type": "CardType",
    "cards.is_day": "IsDay",
}

ATTENDANCE_SCHEMA_DEFAULTS: dict[str, str] = {
    # ستون‌های تکمیلی جدول تردد (جدول/کد پرسنلی/تاریخ/ساعت در بالای همین تب است)
    "datafile.id": "Id",
    "datafile.status": "Status",
    "datafile.duration": "Duration",
    "datafile.prev_day": "PrevDay",
    "datafile.application_id": "ApplicationId",
    "datafile.checksum": "Checksum",
    "datafile.branch_code": "BranchCode",
    # فقط برای درج تردد فراموش‌شده
    "datafile.modify": "Modify",
    "datafile.direction": "Direction",
    "datafile.vt": "VT",
    "datafile.ac": "AC",
    # لاگ تغییر ترددها
    "log_datafile.table": "LogDataFile",
    "log_datafile.id": "Id",
    "log_datafile.user_id": "UserId",
    "log_datafile.application_id": "ApplicationId",
    "log_datafile.username": "Username",
    "log_datafile.additional_info": "AddictionInformation",
    "log_datafile.edit_date": "EditDate",
    "log_datafile.edit_time": "EditTime",
    "log_datafile.io_date": "IoDate",
    "log_datafile.emp_no": "Emp_No",
    "log_datafile.old_time": "OldTime",
    "log_datafile.new_time": "NewTime",
    "log_datafile.old_duration": "OldDuration",
    "log_datafile.new_duration": "NewDuration",
    "log_datafile.old_status": "OldStatus",
    "log_datafile.new_status": "NewStatus",
    "log_datafile.old_prev_day": "OldPrevDay",
    "log_datafile.new_prev_day": "NewPrevDay",
    "log_datafile.old_vt": "OldVT",
    "log_datafile.new_vt": "NewVT",
    "log_datafile.old_ac": "OldAC",
    "log_datafile.new_ac": "NewAC",
    "log_datafile.branch_code": "BranchCode",
    # کارکرد روزانه (فقط شماره شیفت هر روز خوانده می‌شود)
    "daily_work.table": "DailyWork",
    "daily_work.emp_no": "Emp_No",
    "daily_work.date": "Date",
    "daily_work.shift_no": "Shift_No",
    # شیفت‌ها
    "shifts.table": "Shifts",
    "shifts.shift_no": "Shift_No",
    "shifts.kasr_gh": "Kasr_Gh",
    "shifts.kasr_gh5": "Kasr_Gh5",
    # تقویم شیفت گروهی
    "grp_shift.table": "GrpShift",
    "grp_shift.grp_no": "Grp_No",
    "grp_shift.year": "Year",
    "grp_shift.month": "Month",
    "grp_shift.day_prefix": "D",
    # گروه شیفت هر پرسنل در هر تاریخ
    "emp_grps.table": "EmpGrps",
    "emp_grps.emp_no": "Emp_No",
    "emp_grps.date": "Date",
    "emp_grps.new_grp_no": "NewGrp_No",
}

# گروه‌هایی که جدول خودشان را ندارند (ستون‌های تکمیلی یک جدولِ از قبل نگاشت‌شده)
COLUMN_ONLY_GROUPS = {"wf_requests", "wf_reviews", "wf_attachment", "wf_moveup", "wf_parallel", "cards", "datafile"}

# ستون‌هایی که ثبت مرخصی/ماموریت ساعتی روی تردد بدون آن‌ها ممکن نیست
HOURLY_WRITE_COLUMNS = ("id", "status", "duration", "prev_day", "application_id", "checksum", "branch_code")

# ستون‌هایی که درج تردد فراموش‌شده بدون آن‌ها ممکن نیست (همه NOT NULL در کاراوب)
PUNCH_INSERT_COLUMNS = HOURLY_WRITE_COLUMNS + ("modify", "direction", "vt", "ac")

# ستون‌هایی که ثبت ارجاع (سرپرست -> مسئول نیروی انسانی) بدون آن‌ها ممکن نیست
MOVEUP_REQUIRED_COLUMNS = ("request_id", "date", "from_manager", "to_manager")

_SAFE_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_ ]{0,127}$")


def _group(key: str) -> str:
    return key.split(".", 1)[0]


def validate_schema(values: dict | None, defaults: dict[str, str]) -> dict[str, str]:
    """
    فقط کلیدهای شناخته‌شده و نام‌های امن (برای جلوگیری از تزریق در نام
    جدول/ستون). در گروه‌های جدول‌دار: اگر جدول خالی است کل گروه حذف
    می‌شود؛ اگر پر است همه ستون‌هایش باید پر باشند.
    """
    cleaned: dict[str, str] = {}
    for key, value in (values or {}).items():
        if key not in defaults:
            continue
        value = (value or "").strip()
        if not value:
            continue
        if not _SAFE_NAME.match(value):
            raise ValueError(f"نام «{value}» برای «{key}» مجاز نیست (فقط حروف انگلیسی، عدد و زیرخط)")
        cleaned[key] = value

    table_groups = {_group(k) for k in defaults if k.endswith(".table")}
    for group in table_groups:
        if f"{group}.table" not in cleaned:
            for key in [k for k in cleaned if _group(k) == group]:
                del cleaned[key]
            continue
        missing = [k for k in defaults if _group(k) == group and k not in cleaned]
        if missing:
            raise ValueError(f"برای جدول «{cleaned[f'{group}.table']}» همه ستون‌ها باید پر شوند (خالی: {', '.join(missing)})")
    return cleaned


class KaraNames:
    """
    نام‌های نگاشت‌شده (با کوته SQL Server) + تشخیص اینکه هر قابلیت فعال است یا نه.
    هر دو نگاشت اختیاری‌اند - قابلیتی که نگاشتش نیست، فعال نمی‌شود.
    """

    def __init__(self, leave_mapping=None, attendance_mapping=None):
        self.leave = leave_mapping
        self.attendance = attendance_mapping
        self._names: dict[str, str] = {}
        self._names.update(getattr(attendance_mapping, "kara_schema", None) or {})
        self._names.update(getattr(leave_mapping, "kara_schema", None) or {})

    # ---------- دسترسی عمومی ----------

    def has(self, group: str, role: str | None = None) -> bool:
        if role is None:
            return bool(self._names.get(f"{group}.table"))
        return bool(self._names.get(f"{group}.{role}"))

    def raw(self, group: str, role: str) -> str:
        name = self._names.get(f"{group}.{role}")
        if not name:
            raise RuntimeError(f"«{group}.{role}» در تنظیمات سایت نگاشت نشده است")
        return name

    def c(self, group: str, role: str) -> str:
        return f"[{self.raw(group, role)}]"

    def t(self, group: str) -> str:
        return self.c(group, "table")

    @staticmethod
    def _q(name: str | None, what: str) -> str:
        if not name:
            raise RuntimeError(f"«{what}» در تنظیمات سایت نگاشت نشده است")
        return f"[{name}]"

    # ---------- نام‌هایی که از قبل در نگاشت‌های اصلی هستند ----------

    @property
    def requests_table(self) -> str:
        return self._q(getattr(self.leave, "table_name", None), "جدول درخواست‌ها")

    @property
    def requests_id(self) -> str:
        return self._q(getattr(self.leave, "request_id_column", None), "ستون شناسه درخواست")

    @property
    def employee_table(self) -> str:
        return self._q(getattr(self.leave, "employee_table_name", None), "جدول پرسنل")

    @property
    def employee_emp_no(self) -> str:
        return self._q(getattr(self.leave, "employee_emp_no_column", None), "ستون کد پرسنلی جدول پرسنل")

    @property
    def employee_sec_no(self) -> str:
        return self._q(getattr(self.leave, "employee_sec_no_column", None), "ستون واحد جدول پرسنل")

    @property
    def cards_table(self) -> str:
        return self._q(getattr(self.leave, "card_lookup_table_name", None), "جدول کارت‌ها")

    @property
    def cards_no(self) -> str:
        return self._q(getattr(self.leave, "card_lookup_id_column", None), "ستون شماره کارت")

    @property
    def cards_title(self) -> str:
        return self._q(getattr(self.leave, "card_lookup_desc_column", None), "ستون عنوان کارت")

    # جدول تردد: همان نگاشت تب «نگاشت تردد» (فقط روش یک ستون تاریخ + یک ستون ساعت)
    @property
    def has_punch_table(self) -> bool:
        a = self.attendance
        mode = getattr(getattr(a, "mapping_mode", None), "value", getattr(a, "mapping_mode", None))
        return bool(
            a is not None
            and mode == "single_column"
            and a.table_name
            and a.personnel_code_column
            and a.date_column
            and a.time_column
        )

    @property
    def df_table(self) -> str:
        return self._q(getattr(self.attendance, "table_name", None), "جدول تردد")

    @property
    def df_emp_no(self) -> str:
        return self._q(getattr(self.attendance, "personnel_code_column", None), "ستون کد پرسنلی جدول تردد")

    @property
    def df_date(self) -> str:
        return self._q(getattr(self.attendance, "date_column", None), "ستون تاریخ جدول تردد")

    @property
    def df_time(self) -> str:
        return self._q(getattr(self.attendance, "time_column", None), "ستون ساعت جدول تردد")

    # ---------- کدام قابلیت‌ها فعال‌اند ----------

    @property
    def has_employee_section(self) -> bool:
        leave = self.leave
        return bool(
            leave is not None
            and leave.employee_table_name
            and leave.employee_emp_no_column
            and leave.employee_sec_no_column
        )

    @property
    def has_cards(self) -> bool:
        leave = self.leave
        return bool(leave is not None and leave.card_lookup_table_name and leave.card_lookup_id_column)

    @property
    def can_write_daily(self) -> bool:
        """ثبت مرخصی/ماموریت روزانه در جدول مرخصی/ماموریت کاراوب."""
        return self.has("users") and self.has("mor_mam")

    @property
    def can_write_hourly(self) -> bool:
        """اعمال مرخصی/ماموریت ساعتی روی تردد مطابق."""
        return (
            self.has("users")
            and self.has_punch_table
            and all(self.has("datafile", role) for role in HOURLY_WRITE_COLUMNS)
        )

    @property
    def can_write_punch(self) -> bool:
        """درج تردد فراموش‌شده (پس از تأیید نهایی) در جدول تردد."""
        return (
            self.has("users")
            and self.has_punch_table
            and all(self.has("datafile", role) for role in PUNCH_INSERT_COLUMNS)
        )

    @property
    def can_write_moveup(self) -> bool:
        """ثبت ردیف ارجاع در جدول صعود/ارجاع کاراوب."""
        return bool(getattr(self.leave, "wf_moveup_table_name", None)) and all(
            self.has("wf_moveup", role) for role in MOVEUP_REQUIRED_COLUMNS
        )

    @property
    def can_read_hourly_marks(self) -> bool:
        return self.has_punch_table and self.has("datafile", "status")

    @property
    def can_read_daily_marks(self) -> bool:
        return self.has("mor_mam") and self.has_cards and self.has("cards", "is_day")

    @property
    def can_read_work_calendar(self) -> bool:
        return self.has("daily_work") and self.has("shifts")
