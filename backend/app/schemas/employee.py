"""Schema خروجی Employee (فقط برای خواندن — Sync Engine مسئول ساخت/به‌روزرسانی است)."""
from pydantic import BaseModel, ConfigDict


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
