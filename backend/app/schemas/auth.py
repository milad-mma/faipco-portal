"""
Schemaهای Pydantic برای endpointهای احراز هویت (app/api/v1/endpoints/auth.py):
ورود، تمدید توکن، تغییر رمز، بازنشانی رمز و به‌روزرسانی اطلاعات تماس.
"""
from pydantic import BaseModel, EmailStr, Field, field_validator


class LoginRequest(BaseModel):
    """بدنه‌ی POST /auth/login (username = یوزرنیم یا کد پرسنلی، password = رمز یا کد ملی)."""
    username: str
    password: str = Field(min_length=1)
    captcha_id: str | None = Field(default=None, max_length=36)  # وقتی پاسخ قبلی captcha_required داشت
    captcha_answer: str | None = Field(default=None, max_length=20)


class RefreshRequest(BaseModel):
    """بدنه‌ی POST /auth/refresh."""
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    """
    بدنه‌ی PUT /auth/me/password. اگر کاربر کانال OTP دارد (GET /auth/me/password/otp-options → otp_required)،
    otp_code لازم است و current_password نادیده گرفته می‌شود؛ وگرنه current_password لازم است.
    """
    current_password: str | None = Field(default=None, max_length=256)
    otp_code: str | None = Field(default=None, max_length=20)
    new_password: str = Field(min_length=6)


class PasswordOtpRequest(BaseModel):
    """بدنه‌ی POST /auth/me/password/otp: کانال ارسال کد تغییر رمز."""
    channel: str = Field(pattern="^(sms|email)$")


class MobileOtpRequest(BaseModel):
    """بدنه‌ی POST /auth/me/mobile/otp: شماره‌ی موبایل جدید که کد به آن فرستاده می‌شود."""
    mobile: str = Field(min_length=1, max_length=32)


class ForgotPasswordRequest(BaseModel):
    """بدنه‌ی POST /auth/forgot-password."""
    identifier: str = Field(min_length=1)  # نام‌کاربری یا کد پرسنلی - همان دو روش ورود
    channel: str = Field(default="sms", pattern="^(email|sms)$")  # کانال ارسال: email یا sms
    captcha_id: str | None = Field(default=None, max_length=36)  # اگر کپچای فراموشی رمز روشن باشد الزامی است
    captcha_answer: str | None = Field(default=None, max_length=20)


class VerifyResetCodeRequest(BaseModel):
    """بدنه‌ی POST /auth/verify-reset-code. identifier (شناسه‌ی ورود) برای کد ۶ رقمی پیامکی الزامی است."""
    token: str = Field(min_length=1, max_length=128)
    identifier: str | None = Field(default=None, max_length=255)  # نام‌کاربری یا کد پرسنلی که در مرحله‌ی قبل وارد شده


class ResetPasswordRequest(BaseModel):
    """بدنه‌ی POST /auth/reset-password. identifier برای کد ۶ رقمی پیامکی الزامی است (لینک ایمیل: اختیاری)."""
    token: str = Field(min_length=1, max_length=128)
    new_password: str = Field(min_length=6)
    identifier: str | None = Field(default=None, max_length=255)


class ContactInfoUpdateRequest(BaseModel):
    """
    بدنه‌ی PUT /auth/me/contact-info؛ موبایل اجباری است (منبع اصلی اطلاع‌رسانی/بازیابی حساب) و ایمیل اختیاری.
    تغییر ایمیل تأیید نمی‌خواهد. تغییر موبایل: mobile_otp_code (کد پیامک‌شده به شماره‌ی جدید)؛ فقط اگر سرویس
    پیامک خاموش باشد، به‌جای آن current_password (برای پرسنل بدون رمز اختصاصی = کد ملی) لازم است.
    """

    email: EmailStr | None = None
    mobile: str = Field(min_length=1, max_length=32)
    current_password: str | None = Field(default=None, max_length=256)
    mobile_otp_code: str | None = Field(default=None, max_length=20)

    @field_validator("email", mode="before")
    @classmethod
    def _empty_email_is_none(cls, value):
        """فیلد ایمیلِ خالی در فرم («» یا فاصله) یعنی «ایمیل ندارم»، نه ایمیل نامعتبر (قبلاً 422 و صفحه‌ی سفید)."""
        if isinstance(value, str) and not value.strip():
            return None
        return value.strip() if isinstance(value, str) else value


class TokenResponse(BaseModel):
    """پاسخ POST /auth/login و POST /auth/refresh: جفت توکن access و refresh."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
