"""Schemas مربوط به قابلیت «خودروهای من»."""
from datetime import datetime

from pydantic import BaseModel, Field, field_validator


class VehicleIn(BaseModel):
    """ورودی ثبت/ویرایش یک خودرو — چه خودِ کاربر (self-service) چه Admin."""

    vehicle_type: str = Field(min_length=1, max_length=100, description="نوع/مدل خودرو")
    color: str = Field(min_length=1, max_length=50, description="رنگ خودرو")
    plate_digits1: str = Field(description="۲ رقم سمت راست پلاک")
    plate_letter: str = Field(description="حرف فارسی وسط پلاک")
    plate_digits2: str = Field(description="۳ رقم سمت چپ حرف")
    plate_iran_code: str = Field(description="۲ رقم کد ایران")

    @field_validator("plate_digits1", "plate_iran_code")
    @classmethod
    def validate_two_digits(cls, v: str) -> str:
        if not v.isdigit() or len(v) != 2:
            raise ValueError("باید دقیقاً ۲ رقم باشد")
        return v

    @field_validator("plate_digits2")
    @classmethod
    def validate_three_digits(cls, v: str) -> str:
        if not v.isdigit() or len(v) != 3:
            raise ValueError("باید دقیقاً ۳ رقم باشد")
        return v

    @field_validator("plate_letter")
    @classmethod
    def validate_letter(cls, v: str) -> str:
        if len(v) != 1 or not ("\u0600" <= v <= "\u06ff"):
            raise ValueError("باید دقیقاً یک حرف فارسی باشد")
        return v


class VehicleOut(BaseModel):
    """خروجی برای خودِ کاربر — فقط خودروهای خودش."""

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
    """خروجی گزارش Admin/حراست — به‌علاوه هویت پرسنل."""

    employee_id: int
    employee_name: str
    personnel_code: str
    site_name: str | None = None
    department_name: str | None = None
