"""
Schemaهای Pydantic برای endpointهای احراز هویت (app/api/v1/endpoints/auth.py):
ورود، تمدید توکن، تغییر رمز، بازنشانی رمز و به‌روزرسانی اطلاعات تماس.
"""
from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    """بدنه‌ی POST /auth/login (username = یوزرنیم یا کد پرسنلی، password = رمز یا کد ملی)."""
    username: str
    password: str = Field(min_length=1)


class RefreshRequest(BaseModel):
    """بدنه‌ی POST /auth/refresh."""
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    """بدنه‌ی PUT /auth/me/password."""
    current_password: str
    new_password: str = Field(min_length=6)


class ForgotPasswordRequest(BaseModel):
    """بدنه‌ی POST /auth/forgot-password."""
    identifier: str = Field(min_length=1)  # نام‌کاربری یا کد پرسنلی - همان دو روش ورود
    channel: str = Field(default="sms", pattern="^(email|sms)$")  # کانال ارسال: email یا sms


class VerifyResetCodeRequest(BaseModel):
    """بدنه‌ی POST /auth/verify-reset-code."""
    token: str = Field(min_length=1)


class ResetPasswordRequest(BaseModel):
    """بدنه‌ی POST /auth/reset-password."""
    token: str
    new_password: str = Field(min_length=6)


class ContactInfoUpdateRequest(BaseModel):
    """
    بدنه‌ی PUT /auth/me/contact-info؛ موبایل اجباری است (منبع اصلی اطلاع‌رسانی/بازیابی حساب)
    و ایمیل اختیاری.
    """

    email: EmailStr | None = None
    mobile: str = Field(min_length=1)


class TokenResponse(BaseModel):
    """پاسخ POST /auth/login و POST /auth/refresh: جفت توکن access و refresh."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
