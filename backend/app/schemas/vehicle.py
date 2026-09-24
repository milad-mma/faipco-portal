"""
Schemas مربوط به قابلیت «خودروهای من»: ورودی ثبت/ویرایش خودرو با اعتبارسنجی
بخش‌های پلاک ایرانی، خروجی برای خودِ پرسنل و خروجی گزارش Admin.
"""
from datetime import datetime

from pydantic import BaseModel, Field, field_validator

# ۱۶ حرف مجاز پلاک ایران؛ هم‌الگو با PLATE_LETTERS در IranianLicensePlateInput.jsx
# (فرانت‌اند) — این‌جا تکرار شده تا اعتبارسنجی سمت Backend مستقل از فرانت‌اند باشد.
ALLOWED_PLATE_LETTERS = {"ب", "ج", "د", "س", "ص", "ط", "ق", "ل", "م", "ن", "و", "ه", "ی", "ت", "ع", "ا"}


class VehicleIn(BaseModel):
    """بدنه POST /vehicles/me و PATCH /vehicles/{id} — چه خودِ کاربر (self-service) چه Admin."""

    vehicle_type: str = Field(min_length=1, max_length=100, description="نوع/مدل خودرو")
    color: str = Field(min_length=1, max_length=50, description="رنگ خودرو")
    plate_digits1: str = Field(description="۲ رقم سمت راست پلاک")
    plate_letter: str = Field(description="حرف فارسی وسط پلاک")
    plate_digits2: str = Field(description="۳ رقم سمت چپ حرف")
    plate_iran_code: str = Field(description="۲ رقم کد ایران")

    @field_validator("plate_digits1", "plate_iran_code")
    @classmethod
    def validate_two_digits(cls, v: str) -> str:
        """بررسی می‌کند مقدار دقیقاً ۲ رقم باشد."""
        if not v.isdigit() or len(v) != 2:
            raise ValueError("باید دقیقاً ۲ رقم باشد")
        return v

    @field_validator("plate_digits2")
    @classmethod
    def validate_three_digits(cls, v: str) -> str:
        """بررسی می‌کند مقدار دقیقاً ۳ رقم باشد."""
        if not v.isdigit() or len(v) != 3:
            raise ValueError("باید دقیقاً ۳ رقم باشد")
        return v

    @field_validator("plate_letter")
    @classmethod
    def validate_letter(cls, v: str) -> str:
        """بررسی می‌کند حرف پلاک در ALLOWED_PLATE_LETTERS باشد."""
        if v not in ALLOWED_PLATE_LETTERS:
            raise ValueError("حرف پلاک نامعتبر است")
        return v


class VehicleOut(BaseModel):
    """پاسخ GET/POST /vehicles/me و PATCH /vehicles/{id} — خودروهای خودِ کاربر."""

    id: int
    vehicle_type: str
    color: str
    plate_digits1: str
    plate_letter: str
    plate_digits2: str
    plate_iran_code: str
    created_at: datetime

    model_config = {"from_attributes": True}


class VehicleAdminOut(VehicleOut):
    """پاسخ GET /vehicles (گزارش Admin/حراست) — به‌علاوه هویت پرسنل."""

    employee_id: int
    employee_name: str
    personnel_code: str
    site_name: str | None = None
    department_name: str | None = None
