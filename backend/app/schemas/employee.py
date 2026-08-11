"""Schema خروجی Employee (فقط برای خواندن — Sync Engine مسئول ساخت/به‌روزرسانی است)."""
from pydantic import BaseModel, ConfigDict, Field


class EmployeeOut(BaseModel):
    id: int
    personnel_code: str
    national_code: str | None
    first_name: str
    last_name: str
    mobile: str | None
    site_id: int
    department_id: int | None
    is_active: bool  # وضعیت در منبع (فقط توسط Sync Engine تعیین می‌شود؛ غیرقابل‌ویرایش دستی)
    is_enabled: bool  # تصمیم دستی Admin — کاملاً مستقل از Sync، با آن بازنویسی نمی‌شود
    has_custom_password: bool = False  # آیا رمز عبور اختصاصی دارد (یعنی دیگر با کد ملی وارد نمی‌شود)
    # این دو فیلد اختیاری‌اند: فقط GET /employees (که Join با Site/Department دارد)
    # آن‌ها را پر می‌کند؛ Endpoint های دیگر (مثل PATCH) خالی می‌گذارند و فرانت‌اند
    # در آن حالت‌ها از roی lookup محلی خودش (نام سایت/واحد از فهرست جداگانه) استفاده می‌کند.
    site_name: str | None = None
    department_name: str | None = None

    model_config = ConfigDict(from_attributes=True)


class EmployeePageOut(BaseModel):
    """یک صفحه از لیست پرسنل — برای Pagination سمت سرور (به‌جای واکشی صدها/هزاران
    ردیف در یک درخواست)."""

    items: list[EmployeeOut]
    total: int


class EmployeeEnabledUpdate(BaseModel):
    """فعال/غیرفعال‌کردن دستی یک پرسنل از پنل Admin — مستقل از is_active که توسط Sync Engine کنترل می‌شود."""
    is_enabled: bool


class EmployeePasswordSet(BaseModel):
    """برای تعیین دستی رمز عبور ورود یک پرسنل توسط Admin (بعد از این، ورود با کد ملی دیگر کار نمی‌کند)."""
    new_password: str = Field(min_length=6, description="حداقل ۶ کاراکتر")
