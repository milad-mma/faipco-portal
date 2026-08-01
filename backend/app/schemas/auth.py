"""Schema های Pydantic برای Login/Refresh/Token."""
from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str
    password: str = Field(min_length=1)


class EmployeeLoginRequest(BaseModel):
    """ورود پرسنل با کد پرسنلی (به‌جای یوزرنیم) و کد ملی (به‌جای رمز عبور)."""

    personnel_code: str
    national_code: str


class RefreshRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str = Field(min_length=6)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
