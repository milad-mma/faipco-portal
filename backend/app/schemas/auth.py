"""Schema های Pydantic برای Login/Refresh/Token."""
from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    username: str
    password: str = Field(min_length=1)


class RefreshRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=6)


class ForgotPasswordRequest(BaseModel):
    identifier: str = Field(min_length=1)  # نام‌کاربری یا کد پرسنلی - همان دو روش ورود
    channel: str = Field(default="sms", pattern="^(email|sms)$")


class VerifyResetCodeRequest(BaseModel):
    token: str = Field(min_length=1)


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str = Field(min_length=6)


class ContactInfoUpdateRequest(BaseModel):
    """
    موبایل اجباری است (منبع اصلی اطلاع‌رسانی/بازیابی حساب)؛ ایمیل
    اختیاری باقی می‌ماند.
    """

    email: EmailStr | None = None
    mobile: str = Field(min_length=1)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
