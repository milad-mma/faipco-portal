"""
Schema های Pydantic برای سیستم اطلاعیه سازمانی (مورد استفاده در endpointهای /notices).
شامل ورودی ایجاد اطلاعیه، خروجی اطلاعیه برای مخاطب، گزارش‌های فرستنده/Admin،
فهرست بازدیدکنندگان و نتیجه آپلود فیش حقوقی/کارکرد.
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, model_validator

from app.models.notice import NoticePriority, NoticeStatus, NoticeTargetType, NoticeType


class NoticeTargetIn(BaseModel):
    """یک مخاطب در ورودی NoticeCreate (POST /notices)."""
    target_type: NoticeTargetType
    # برای target_type == "all" باید None باشد؛ در غیر این‌صورت شناسه Site/Department/Role/Employee مقصد
    target_id: int | None = None

    @model_validator(mode="after")
    def validate_target_id(self) -> "NoticeTargetIn":
        """سازگاری target_id با target_type را بررسی می‌کند (برای all خالی، برای بقیه الزامی)."""
        if self.target_type == NoticeTargetType.all and self.target_id is not None:
            raise ValueError("برای مخاطب 'all' نباید target_id مقداردهی شود")
        if self.target_type != NoticeTargetType.all and self.target_id is None:
            raise ValueError("برای این نوع مخاطب، target_id الزامی است")
        return self


class NoticeTargetOut(BaseModel):
    """یک مخاطب خام (نوع + شناسه) در خروجی NoticeOut."""
    target_type: NoticeTargetType
    target_id: int | None

    model_config = ConfigDict(from_attributes=True)


class NoticeCreate(BaseModel):
    """ورودی POST /notices برای ایجاد اطلاعیه متنی معمولی."""
    title: str
    body: str
    priority: NoticePriority = NoticePriority.normal
    publish_at: datetime | None = None
    expire_at: datetime | None = None
    targets: list[NoticeTargetIn]

    @model_validator(mode="after")
    def validate_targets(self) -> "NoticeCreate":
        """حداقل یک مخاطب را الزامی می‌کند."""
        if not self.targets:
            raise ValueError("حداقل یک مخاطب برای اطلاعیه الزامی است")
        return self

    @model_validator(mode="after")
    def validate_title_and_body(self) -> "NoticeCreate":
        """خالی نبودن عنوان و متن را بررسی می‌کند."""
        # بررسی روی مقدار strip‌شده انجام می‌شود تا رشته فقط‌فاصله معتبر نباشد؛
        # مقدار ذخیره‌شده بدون strip باقی می‌ماند.
        if not self.title.strip():
            raise ValueError("عنوان اطلاعیه الزامی است")
        if not self.body.strip():
            raise ValueError("متن اطلاعیه الزامی است")
        return self


class NoticeOut(BaseModel):
    """خروجی اطلاعیه در POST /notices، GET /notices و GET /notices/me (با وضعیت شخصی کاربر)."""
    id: int
    sender_id: int
    sender_name: str = "—"  # فقط در /notices/me پر می‌شود (نام فرستنده برای اطلاعیه‌های دریافتی)
    sender_department_name: str | None = None  # همین‌طور فقط در /notices/me — واحد سازمانی فرستنده
    title: str
    body: str
    priority: NoticePriority
    status: NoticeStatus
    notice_type: NoticeType = NoticeType.normal
    publish_at: datetime | None
    expire_at: datetime | None
    created_at: datetime
    targets: list[NoticeTargetOut]
    is_read: bool = False  # فقط در /notices/me معنا دارد؛ جای دیگر همیشه False است
    is_archived: bool = False  # همین‌طور فقط در /notices/me — آیا خودِ همین کاربر آرشیوش کرده
    has_my_payroll_receipt: bool = False  # فقط در /notices/me: آیا فیش حقوقی خودِ من برای این اطلاعیه موجود است
    has_my_attendance_card: bool = False  # همین‌طور فقط در /notices/me: آیا فیش کارکرد خودِ من موجود است

    model_config = ConfigDict(from_attributes=True)


class NoticeTargetDescription(BaseModel):
    """توصیف قابل‌فهم یک Target — مثلاً «کارخانه ۱» به‌جای site_id=۱؛ در NoticeDetailOut استفاده می‌شود."""
    target_type: NoticeTargetType
    target_id: int | None
    label: str


class NoticeDetailOut(BaseModel):
    """برای گزارش‌های «ارسالی من» و «گزارش کامل Admin» — شامل فرستنده، مقصدها و آمار بازدید."""
    id: int
    title: str
    body: str
    priority: NoticePriority
    status: NoticeStatus
    notice_type: NoticeType = NoticeType.normal
    sender_id: int
    sender_name: str
    created_at: datetime
    publish_at: datetime | None
    targets: list[NoticeTargetDescription]
    audience_count: int  # تعداد کل مخاطبان محاسبه‌شده از روی targets
    read_count: int  # تعداد مخاطبانی که اطلاعیه را دیده‌اند
    is_deleted: bool = False
    deleted_at: datetime | None = None


class NoticeDetailPageOut(BaseModel):
    """یک صفحه از گزارش اطلاعیه‌ها (Pagination سمت سرور)؛ خروجی
    /notices/sent-by-me، /notices/admin-report و /notices/site-report."""

    items: list[NoticeDetailOut]
    total: int


class NoticePageOut(BaseModel):
    """یک صفحه از اطلاعیه‌های دریافتی خودِ کاربر جاری (GET /notices/me)
    با Pagination سمت سرور."""

    items: list[NoticeOut]
    total: int
    # تعداد کل اطلاعیه‌های خوانده‌نشده کاربر با همان فیلترها (نه فقط این صفحه)
    unread_total: int = 0


class NoticeReaderOut(BaseModel):
    """یک نفر که اطلاعیه را دیده؛ خروجی GET /notices/{notice_id}/readers (Drill-down گزارش)."""
    user_id: int
    employee_id: int | None
    first_name: str | None
    last_name: str | None
    personnel_code: str | None
    read_at: datetime


class PayrollNoticeResultOut(BaseModel):
    """پاسخ POST /notices/payroll — نتیجه تطبیق کدهای پرسنلی فایل فیش حقوقی برای acc_manager."""
    notice_id: int
    matched_employee_count: int
    missing_codes: list[str]
    invalid_row_count: int
    out_of_scope_codes: list[str] = []  # کدهایی که فقط در سایت‌های خارج از مجوز فرستنده پرسنل دارند (ارسال نشد)


class AttendanceCardResultOut(BaseModel):
    """پاسخ POST /notices/attendance-card — نتیجه تطبیق کدهای پرسنلی فایل کارکرد برای hr-manager."""
    notice_id: int
    matched_employee_count: int
    missing_codes: list[str]
    invalid_row_count: int
    out_of_scope_codes: list[str] = []  # کدهایی که فقط در سایت‌های خارج از مجوز فرستنده پرسنل دارند (ارسال نشد)
