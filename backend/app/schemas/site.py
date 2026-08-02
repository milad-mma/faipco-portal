"""Schema های Pydantic برای مدیریت Site، اتصال دیتابیس و Mapping ستون‌ها."""
from pydantic import BaseModel, ConfigDict, Field

from app.models.site import DbType, SyncStatus


class SiteCreate(BaseModel):
    name: str
    code: str = Field(max_length=32)
    description: str | None = None


class SiteOut(BaseModel):
    id: int
    name: str
    code: str
    description: str | None
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


class SiteConnectionIn(BaseModel):
    db_type: DbType
    host: str
    port: int
    database_name: str
    username: str
    password: str | None = Field(
        default=None,
        description="در حالت ویرایش، خالی بگذارید تا پسورد قبلی حفظ شود",
    )


class SiteConnectionOut(BaseModel):
    id: int
    site_id: int
    db_type: DbType
    host: str
    port: int
    database_name: str
    username: str
    is_active: bool
    last_sync_status: SyncStatus

    model_config = ConfigDict(from_attributes=True)


class EmployeeMappingIn(BaseModel):
    table_name: str
    personnel_code_column: str
    national_code_column: str | None = None
    first_name_column: str
    last_name_column: str
    mobile_column: str | None = None
    is_active_column: str | None = None
    is_active_inverted: bool = False
    department_column: str | None = None
    # اگر جدولی مثل dbo.Sections کد واحد را به نام واقعی‌اش ترجمه می‌کند:
    department_lookup_table: str | None = None
    department_lookup_id_column: str | None = None
    department_lookup_name_column: str | None = None


class EmployeeMappingOut(EmployeeMappingIn):
    id: int
    site_id: int

    model_config = ConfigDict(from_attributes=True)
