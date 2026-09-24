"""
Schemaهای Pydantic برای مدیریت کاربران، نقش‌ها و انتصاب نقش (endpointهای app/api/v1/endpoints/users.py).
"""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class RoleOut(BaseModel):
    """خلاصه‌ی یک نقش؛ پاسخ GET /users/roles."""
    id: int
    name: str
    description: str | None
    is_system: bool

    model_config = ConfigDict(from_attributes=True)


class PermissionOut(BaseModel):
    """یک مجوز؛ پاسخ GET /users/permissions و بخشی از RoleDetailOut."""
    id: int
    code: str
    description: str | None

    model_config = ConfigDict(from_attributes=True)


class RoleDetailOut(RoleOut):
    """جزئیات یک نقش به‌همراه مجوزهایش؛ پاسخ endpointهای /users/role-catalog (صفحه‌ی ویرایش نقش)."""

    permissions: list[PermissionOut]


class RoleUpsertIn(BaseModel):
    """بدنه‌ی ساخت/ویرایش نقش در /users/role-catalog: نام، توضیح و فهرست مجوزها."""

    name: str = Field(min_length=1, max_length=64)
    description: str | None = None
    permission_ids: list[int] = []


class UserRoleOut(BaseModel):
    """یک انتصاب نقش (ردیف user_roles)؛ پاسخ GET/POST /users/{user_id}/roles."""
    id: int
    user_id: int
    role_id: int
    site_id: int | None

    model_config = ConfigDict(from_attributes=True)


class AssignRoleIn(BaseModel):
    """بدنه‌ی POST /users/{user_id}/roles."""
    role_id: int
    # یک انتصاب می‌تواند چند سایت را پوشش دهد؛ برای هر سایت یک ردیف جدا در user_roles ساخته می‌شود
    # (Unique Constraint روی user_id+role_id+site_id)
    site_ids: list[int] = Field(min_length=1)


class BulkAssignRoleIn(BaseModel):
    """
    بدنه‌ی POST /users/bulk-assign-role: انتصاب یک نقش به چند پرسنل، با فهرست employee_ids
    یا با فیلتر همه‌ی پرسنل یک سایت/واحد. حداقل یکی از این دو راه باید داده شود.
    """

    role_id: int
    employee_ids: list[int] | None = None
    site_id: int | None = None
    department_id: int | None = None


class BulkAssignRoleOut(BaseModel):
    """پاسخ POST /users/bulk-assign-role: آمار نتیجه‌ی انتصاب گروهی."""
    assigned_count: int  # چند نفر تازه این نقش را گرفتند
    already_had_count: int  # چند نفر از قبل همین نقش را داشتند (نادیده گرفته شد)
    not_found_count: int  # چند employee_id نامعتبر بود (پیدا نشد)
    total_matched: int  # مجموع پرسنلی که این عملیات رویشان اعمال شد


class AccessOverviewRole(BaseModel):
    """یک نقش در ردیف AccessOverviewEntry."""
    role_name: str
    site_name: str | None  # None یعنی نقش سراسری است


class AccessOverviewDepartment(BaseModel):
    """یک واحد تحت سرپرستی در ردیف AccessOverviewEntry."""
    id: int
    name: str
    site_name: str


class AccessOverviewEntry(BaseModel):
    """یک ردیف از پاسخ GET /users/access-overview: پرسنل با نقش‌ها و واحدهای تحت سرپرستی‌اش."""
    employee_id: int
    first_name: str
    last_name: str
    personnel_code: str
    site_name: str
    roles: list[AccessOverviewRole]
    supervised_departments: list[AccessOverviewDepartment]


class SiteTransferRole(BaseModel):
    """یک نقش فعلی کاربرِ منتقل‌شده در SiteTransferOut."""
    role_name: str
    site_name: str | None  # None یعنی نقش سراسری است
    is_old_site: bool  # نقش مربوط به سایت قبلی است و احتمالاً باید بازبینی شود


class SiteTransferOut(BaseModel):
    """یک جابه‌جایی پرسنل بین سایت‌ها در GET /users/site-transfers، با نقش‌ها و سرپرستی‌های فعلی او."""
    id: int
    employee_id: int
    personnel_code: str
    first_name: str
    last_name: str
    site_id: int  # سایت فعلی پرسنل (برای باز کردن دیالوگ دسترسی)
    from_site_name: str | None
    to_site_name: str | None
    transferred_at: datetime
    reviewed_at: datetime | None
    has_user: bool  # پرسنل حساب کاربری دارد (بدون حساب، نقشی هم ندارد)
    roles: list[SiteTransferRole]
    old_site_departments: list[str]  # واحدهای سایت قبلی که هنوز سرپرستشان است
    other_assignments: list[str] = []  # مسئولیت‌های دیگر در سایت قبلی (مسئول نیروی انسانی، تأییدکننده مرخصی، مدیر ارزیابی، سرشیفت)

