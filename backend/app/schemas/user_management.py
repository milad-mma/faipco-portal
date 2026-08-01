"""Schema های Pydantic برای مدیریت کاربران و انتصاب نقش (بخش مدیریت دسترسی)."""
from pydantic import BaseModel, ConfigDict


class RoleOut(BaseModel):
    id: int
    name: str
    description: str | None
    is_system: bool

    model_config = ConfigDict(from_attributes=True)


class UserManagementOut(BaseModel):
    id: int
    username: str
    email: str | None
    is_active: bool
    is_superuser: bool
    employee_id: int | None

    model_config = ConfigDict(from_attributes=True)


class UserRoleOut(BaseModel):
    id: int
    user_id: int
    role_id: int
    site_id: int | None

    model_config = ConfigDict(from_attributes=True)


class AssignRoleIn(BaseModel):
    role_id: int
    # اگر site_id داده شود، این نقش فقط برای همان Site معتبر است (مثلاً «مدیر سایت ۲»)؛
    # اگر خالی باشد، نقش سراسری است (مثلاً «مدیرعامل» یا «مدیر منابع انسانی»)
    site_id: int | None = None
