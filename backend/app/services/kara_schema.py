"""
نگاشت نام جدول/ستون‌های کاراوب که در هم‌رفتاری با کاراوب (ثبت در کارکرد)
و نمایش مرخصی/ماموریت در گزارش تردد استفاده می‌شوند.

⚠️ طبق درخواست صریح کاربر: هیچ نام جدول/ستونی نباید مستقیم در کد باشد -
همه از تنظیمات سایت (LeaveRequestMapping.kara_schema) خوانده می‌شوند.
مقادیر پیش‌فرض همان نام‌های واقعی کاراوب هستند (با دیتابیس واقعی بررسی
شده)؛ ادمین فقط در صورت تفاوت نصب، مقدار دیگری وارد می‌کند و بقیه از
پیش‌فرض می‌آیند.

کلیدها به شکل «گروه.نقش» هستند؛ «گروه.table» نام جدول است.
"""
from __future__ import annotations

import re

# ترتیب گروه‌ها و فیلدها همان ترتیب نمایش در پنل تنظیمات است
KARA_SCHEMA_DEFAULTS: dict[str, str] = {
    # ستون‌های تکمیلی خودِ جدول درخواست (نام جدول/شناسه در نگاشت اصلی است)
    "wf_requests.submitted_by": "SubmittedByEmployeeID",
    "wf_requests.requested_time": "Requested_Time",
    "wf_requests.accept_code": "AcceptCode",
    "wf_requests.cur_section": "CurSection",
    "wf_requests.duty_tools": "DutyTools",
    "wf_requests.duty_tamin": "DutyTamin",
    # جدول‌های وابسته درخواست (نام جدول‌ها در نگاشت اصلی است)
    "wf_reviews.id": "Id",
    "wf_attachment.request_id": "RequestId",
    "wf_moveup.request_id": "RequestId",
    "wf_parallel.request_id": "RequestId",
    "wf_request_state.table": "WF_RequestState",
    "wf_request_state.request_id": "RequestId",
    # کاربران کاراوب (ثبت‌کننده تغییر در لاگ‌ها)
    "users.table": "Users",
    "users.user_id": "UserId",
    "users.username": "Username",
    "users.emp_no": "Emp_No",
    "users.is_active": "IsActive",
    "users.creation_date": "CreationDate",
    # ترددها
    "datafile.table": "DataFile",
    "datafile.id": "Id",
    "datafile.emp_no": "Emp_No",
    "datafile.date": "Date",
    "datafile.time": "Time",
    "datafile.status": "Status",
    "datafile.duration": "Duration",
    "datafile.prev_day": "PrevDay",
    "datafile.application_id": "ApplicationId",
    "datafile.checksum": "Checksum",
    "datafile.branch_code": "BranchCode",
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
    # کارت‌ها (نام جدول/شماره/عنوان در نگاشت اصلی «جدول Cards» است)
    "cards.card_type": "CardType",
    "cards.is_day": "IsDay",
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
    # گروه هر پرسنل در هر تاریخ
    "emp_grps.table": "EmpGrps",
    "emp_grps.emp_no": "Emp_No",
    "emp_grps.date": "Date",
    "emp_grps.new_grp_no": "NewGrp_No",
}

# نام مجاز: حروف/عدد/زیرخط/فاصله - برای جلوگیری از هر نوع تزریق در نام
# جدول/ستون (مقادیر همیشه Parameterized هستند؛ نام‌ها نمی‌توانند باشند)
_SAFE_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_ ]{0,127}$")


def validate_kara_schema(overrides: dict | None) -> dict[str, str]:
    """فقط کلیدهای شناخته‌شده و نام‌های امن؛ مقدار خالی یعنی «همان پیش‌فرض»."""
    cleaned: dict[str, str] = {}
    for key, value in (overrides or {}).items():
        if key not in KARA_SCHEMA_DEFAULTS:
            continue
        value = (value or "").strip()
        if not value or value == KARA_SCHEMA_DEFAULTS[key]:
            continue
        if not _SAFE_NAME.match(value):
            raise ValueError(f"نام «{value}» برای «{key}» مجاز نیست (فقط حروف انگلیسی، عدد و زیرخط)")
        cleaned[key] = value
    return cleaned


def effective_kara_schema(overrides: dict | None) -> dict[str, str]:
    return {**KARA_SCHEMA_DEFAULTS, **{k: v for k, v in (overrides or {}).items() if k in KARA_SCHEMA_DEFAULTS and v}}


class KaraNames:
    """
    نام‌های نهایی (پیش‌فرض + تنظیمات سایت) با کوته SQL Server.
    t("mor_mam") -> [Mor_Mam]، c("mor_mam", "emp_no") -> [Emp_No]،
    raw(...) بدون کوته (برای پیشوند ستون‌های روز GrpShift).
    """

    def __init__(self, mapping):
        self._names = effective_kara_schema(getattr(mapping, "kara_schema", None))
        self.mapping = mapping

    def raw(self, group: str, role: str) -> str:
        return self._names[f"{group}.{role}"]

    def c(self, group: str, role: str) -> str:
        return f"[{self.raw(group, role)}]"

    def t(self, group: str) -> str:
        return self.c(group, "table")

    # --- نام‌هایی که از قبل در نگاشت اصلی درخواست مرخصی/ماموریت هستند ---
    @staticmethod
    def _q(name: str | None, what: str = "") -> str:
        if not name:
            raise RuntimeError(f"«{what}» در تنظیمات درخواست مرخصی/ماموریت این سایت تعیین نشده است")
        return f"[{name}]"

    @property
    def requests_table(self) -> str:
        return self._q(self.mapping.table_name, "جدول درخواست‌ها")

    @property
    def requests_id(self) -> str:
        return self._q(self.mapping.request_id_column, "ستون شناسه درخواست")

    @property
    def employee_table(self) -> str:
        return self._q(self.mapping.employee_table_name, "جدول پرسنل")

    @property
    def employee_emp_no(self) -> str:
        return self._q(self.mapping.employee_emp_no_column, "ستون کد پرسنلی جدول پرسنل")

    @property
    def employee_sec_no(self) -> str:
        return self._q(self.mapping.employee_sec_no_column, "ستون واحد جدول پرسنل")

    @property
    def cards_table(self) -> str:
        return self._q(self.mapping.card_lookup_table_name, "جدول کارت‌ها")

    @property
    def cards_no(self) -> str:
        return self._q(self.mapping.card_lookup_id_column, "ستون شماره کارت")

    @property
    def cards_title(self) -> str:
        return self._q(self.mapping.card_lookup_desc_column, "ستون عنوان کارت")
