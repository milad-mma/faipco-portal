"""Schema های Pydantic برای مدیریت کاربران و انتصاب نقش (بخش مدیریت دسترسی)."""
from pydantic import BaseModel, ConfigDict, Field


class RoleOut(BaseModel):
    id: int
    name: str
    description: str | None
    is_system: bool

    model_config = ConfigDict(from_attributes=True)


class PermissionOut(BaseModel):
    id: int
    code: str
    description: str | None

    model_config = ConfigDict(from_attributes=True)


class RoleDetailOut(RoleOut):
    """جزئیات یک نقش به‌همراه مجوزهایش — برای صفحه ویرایش نقش."""

    permissions: list[PermissionOut]


class RoleUpsertIn(BaseModel):
    """ساخت یا ویرایش یک نقش — نام + توضیح + فهرست مجوزهایی که باید داشته باشد."""

    name: str = Field(min_length=1, max_length=64)
    description: str | None = None
    permission_ids: list[int] = []


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


class BulkAssignRoleIn(BaseModel):
    """
    انتصاب یک نقش به چند پرسنل هم‌زمان — یا با فهرست دقیق employee_id ها،
    یا با فیلتر (همه پرسنل یک سایت/واحد). حداقل یکی از این دو راه باید داده شود.
    """

    role_id: int
    employee_ids: list[int] | None = None
    site_id: int | None = None
    department_id: int | None = None


class BulkAssignRoleOut(BaseModel):
    assigned_count: int  # چند نفر تازه این نقش را گرفتند
    already_had_count: int  # چند نفر از قبل همین نقش را داشتند (نادیده گرفته شد)
    not_found_count: int  # چند employee_id نامعتبر بود (پیدا نشد)
    total_matched: int  # مجموع پرسنلی که این عملیات رویشان اعمال شد


class AccessOverviewRole(BaseModel):
    role_name: str
    site_name: str | None  # None یعنی نقش سراسری است


class AccessOverviewDepartment(BaseModel):
    id: int
    name: str
    site_name: str


class AccessOverviewEntry(BaseModel):
    employee_id: int
    first_name: str
    last_name: str
    personnel_code: str
    site_name: str
    roles: list[AccessOverviewRole]
    supervised_departments: list[AccessOverviewDepartment]
