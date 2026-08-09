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
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class EmployeeActiveUpdate(BaseModel):
    """برای فعال/غیرفعال‌کردن دستی یک پرسنل از پنل Admin (جدا از منطق خودکار Sync Engine)."""
    is_active: bool


class EmployeePasswordSet(BaseModel):
    """برای تعیین دستی رمز عبور ورود یک پرسنل توسط Admin."""
    new_password: str = Field(min_length=6, description="حداقل ۶ کاراکتر")
