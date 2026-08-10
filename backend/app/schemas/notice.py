"""Schema های Pydantic برای سیستم اطلاعیه سازمانی."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, model_validator

from app.models.notice import NoticePriority, NoticeStatus, NoticeTargetType, NoticeType


class NoticeTargetIn(BaseModel):
    target_type: NoticeTargetType
    # برای target_type == "all" باید None باشد؛ در غیر این‌صورت شناسه Site/Department/Role/Employee مقصد
    target_id: int | None = None

    @model_validator(mode="after")
    def validate_target_id(self) -> "NoticeTargetIn":
        if self.target_type == NoticeTargetType.all and self.target_id is not None:
            raise ValueError("برای مخاطب 'all' نباید target_id مقداردهی شود")
        if self.target_type != NoticeTargetType.all and self.target_id is None:
            raise ValueError("برای این نوع مخاطب، target_id الزامی است")
        return self


class NoticeTargetOut(BaseModel):
    target_type: NoticeTargetType
    target_id: int | None

    model_config = ConfigDict(from_attributes=True)


class NoticeCreate(BaseModel):
    title: str
    body: str
    priority: NoticePriority = NoticePriority.normal
    publish_at: datetime | None = None
    expire_at: datetime | None = None
    targets: list[NoticeTargetIn]

    @model_validator(mode="after")
    def validate_targets(self) -> "NoticeCreate":
        if not self.targets:
            raise ValueError("حداقل یک مخاطب برای اطلاعیه الزامی است")
        return self


class NoticeOut(BaseModel):
    id: int
    sender_id: int
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
    has_my_payroll_receipt: bool = False  # فقط در /notices/me: آیا فیش حقوقی خودِ من برای این اطلاعیه موجود است

    model_config = ConfigDict(from_attributes=True)


class NoticeTargetDescription(BaseModel):
    """توصیف قابل‌فهم یک Target — مثلاً «کارخانه ۱» به‌جای site_id=۱."""
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
    audience_count: int
    read_count: int
    is_deleted: bool = False
    deleted_at: datetime | None = None


class NoticeReaderOut(BaseModel):
    """یک نفر که یک اطلاعیه مشخص را دیده — برای درون‌رفت (Drill-down) به جزئیات."""
    user_id: int
    employee_id: int | None
    first_name: str | None
    last_name: str | None
    personnel_code: str | None
    read_at: datetime


class PayrollNoticeResultOut(BaseModel):
    """پاسخ آپلود فیش حقوقی — برای اطلاع فوری acc_manager از نتیجه تطبیق کدها."""
    notice_id: int
    matched_employee_count: int
    missing_codes: list[str]
    invalid_row_count: int
