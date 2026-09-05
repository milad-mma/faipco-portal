"""Schema های Pydantic برای مدیریت Site، اتصال دیتابیس و Mapping ستون‌ها."""
from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.models.site import AttendanceMappingMode, DbType, SyncStatus


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

    دو روش نگاشت پشتیبانی می‌شوند (mapping_mode):
    - single_column: یک ردیف = یک تردد منفرد؛ date_column/time_column
      الزامی‌اند (enter_*/exit_* باید خالی بمانند).
    - enter_exit_columns: یک ردیف = یک نشست کامل (ورود+خروج)؛ هر چهار
      ستون enter_date_column/enter_time_column/exit_date_column/
      exit_time_column الزامی‌اند (date_column/time_column باید خالی
      بمانند).
    """

    table_name: str
    personnel_code_column: str
    mapping_mode: AttendanceMappingMode = AttendanceMappingMode.single_column

    date_column: str | None = None
    time_column: str | None = None

    enter_date_column: str | None = None
    enter_time_column: str | None = None
    exit_date_column: str | None = None
    exit_time_column: str | None = None

    # نگاشت اختیاری جدول تقویم/تعطیلات — برای رنگ‌آمیزی روزهای تعطیل.
    # اگر calendar_table_name خالی/None باشد، این قابلیت غیرفعال می‌ماند.
    calendar_table_name: str | None = None
    calendar_year_column: str | None = None
    calendar_month_column: str | None = None
    calendar_day_column_prefix: str | None = None

    @model_validator(mode="after")
    def _validate_columns_for_mode(self) -> "AttendanceMappingIn":
        if self.mapping_mode == AttendanceMappingMode.single_column:
            if not (self.date_column and self.time_column):
                raise ValueError("برای روش «یک ستون تاریخ + یک ستون ساعت»، هر دو فیلد الزامی هستند")
        else:
            if not (
                self.enter_date_column and self.enter_time_column and self.exit_date_column and self.exit_time_column
            ):
                raise ValueError("برای روش «ستون‌های جدای ورود/خروج»، هر چهار فیلد الزامی هستند")
        return self


class AttendanceMappingOut(AttendanceMappingIn):
    id: int
    site_id: int

    model_config = ConfigDict(from_attributes=True)
