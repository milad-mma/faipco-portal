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
    gps_latitude: float | None = None
    gps_longitude: float | None = None
    gps_radius_meters: int | None = None

    model_config = ConfigDict(from_attributes=True)


class SiteGpsLocationIn(BaseModel):
    """تنظیم/پاک‌کردن موقعیت GPS یک سایت — هر سه فیلد با هم NULL یا با هم
    مقداردار می‌شوند (یا موقعیت کامل تنظیم شده یا اصلاً تنظیم نشده)."""

    gps_latitude: float | None = None
    gps_longitude: float | None = None
    gps_radius_meters: int | None = None


class SiteActiveUpdate(BaseModel):
    """فعال/غیرفعال‌کردن یک Site — برای علامت‌گذاری سریع یک کارخانه/شعبه به‌عنوان
    غیرفعال (مثلاً هنگام تعطیلی موقت) بدون نیاز به حذف کامل آن."""

    is_active: bool



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


class SiteConnectionActiveUpdate(BaseModel):
    """روشن/خاموش‌کردن همگام‌سازی خودکار این Site — بدون نیاز به حذف یا ویرایش
    مجدد اطلاعات اتصال دیتابیس (Host/Username/Password و ...)."""

    is_active: bool


class EmployeeMappingIn(BaseModel):
    table_name: str
    personnel_code_column: str
    national_code_column: str | None = None
    first_name_column: str
    last_name_column: str
    mobile_column: str | None = None
    email_column: str | None = None
    birth_date_column: str | None = None
    is_active_column: str | None = None
    is_active_inverted: bool = False
    department_column: str | None = None
    # اگر جدولی مثل dbo.Sections کد واحد را به نام واقعی‌اش ترجمه می‌کند:
    department_lookup_table: str | None = None
    department_lookup_id_column: str | None = None
    department_lookup_name_column: str | None = None
    # اختیاری: نگاشت سمت/عنوان شغلی — دقیقاً همان الگوی واحد سازمانی بالا
    position_column: str | None = None
    position_lookup_table: str | None = None
    position_lookup_id_column: str | None = None
    position_lookup_name_column: str | None = None
    # اختیاری: نگاشت جدول عکس پرسنل (EmployeeExtendedInfo)
    photo_table: str | None = None
    photo_emp_no_column: str | None = None
    photo_thumbnail_column: str | None = None


class EmployeeMappingOut(EmployeeMappingIn):
    id: int
    site_id: int

    model_config = ConfigDict(from_attributes=True)


class AttendanceMappingIn(BaseModel):
    """
    نگاشت جدول/ستون‌های تردد دستگاهی این سایت — دقیقاً همان الگوی
    EmployeeMappingIn بالا، فقط برای «گزارش تردد ماهانه».
    """

    table_name: str
    personnel_code_column: str
    date_column: str
    time_column: str

    # نگاشت اختیاری جدول تقویم/تعطیلات — برای رنگ‌آمیزی روزهای تعطیل.
    # اگر calendar_table_name خالی/None باشد، این قابلیت غیرفعال می‌ماند.
    calendar_table_name: str | None = None
    calendar_year_column: str | None = None
    calendar_month_column: str | None = None
    calendar_day_column_prefix: str | None = None


class AttendanceMappingOut(AttendanceMappingIn):
    id: int
    site_id: int

    model_config = ConfigDict(from_attributes=True)
