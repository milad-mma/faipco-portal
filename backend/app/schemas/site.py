"""
Schema های Pydantic برای مدیریت Site: ایجاد/نمایش سایت، GPS و وضعیت فعال بودن،
اطلاعات اتصال دیتابیس منبع، نگاشت ستون‌های پرسنل و نگاشت جدول تردد/تقویم.
"""
from pydantic import BaseModel, ConfigDict, Field, model_validator, field_validator

from app.services.kara_schema import ATTENDANCE_SCHEMA_DEFAULTS, validate_schema

from app.models.site import AttendanceMappingMode, DbType, SyncStatus


class SiteCreate(BaseModel):
    """ورودی ایجاد سایت جدید (POST /sites)."""

    name: str
    code: str = Field(max_length=32)
    description: str | None = None


class SiteOut(BaseModel):
    """خروجی اطلاعات یک سایت در Endpoint های /sites."""

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
    """ورودی ثبت/ویرایش اطلاعات اتصال دیتابیس منبع سایت (PUT /sites/{id}/connection)."""

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
    """خروجی اطلاعات اتصال سایت (بدون رمز عبور)."""

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
    """ورودی نگاشت جدول/ستون‌های پرسنل دیتابیس منبع به فیلدهای Employee (PUT /sites/{id}/mapping)."""

    table_name: str
    personnel_code_column: str
    national_code_column: str | None = None
    first_name_column: str
    last_name_column: str
    mobile_column: str | None = None
    email_column: str | None = None
    birth_date_column: str | None = None
    hire_date_column: str | None = None
    gender_column: str | None = None
    is_active_column: str | None = None
    is_active_inverted: bool = False
    # اختیاری: فیلتر شعبه برای دیتابیس پرسنل مشترک بین چند سایت (مثل BranchCode)
    branch_code_column: str | None = None
    branch_code_value: str | None = None
    department_column: str | None = None
    # اگر جدولی مثل dbo.Sections کد واحد را به نام واقعی‌اش ترجمه می‌کند:
    department_lookup_table: str | None = None
    department_lookup_id_column: str | None = None
    department_lookup_name_column: str | None = None
    # اختیاری: ستون واحد بالادست در جدول واحدها (کاراوب: TFather) و واحدهای ریشه‌ی این سایت
    # (برای چند سایت با یک دیتابیس منبع مشترک؛ فهرست خالی = بدون فیلتر درختی)
    department_lookup_parent_column: str | None = None
    root_department_codes: list[str] = Field(default_factory=list)
    # اختیاری: نگاشت سمت/عنوان شغلی — دقیقاً همان الگوی واحد سازمانی بالا
    position_column: str | None = None
    position_lookup_table: str | None = None
    position_lookup_id_column: str | None = None
    position_lookup_name_column: str | None = None
    # اختیاری: نگاشت جدول عکس پرسنل (EmployeeExtendedInfo)
    photo_table: str | None = None
    photo_emp_no_column: str | None = None
    photo_thumbnail_column: str | None = None


    @field_validator("root_department_codes", mode="before")
    @classmethod
    def _clean_roots(cls, value):
        """کدهای ریشه را به رشته‌ی trim‌شده تبدیل می‌کند و موارد خالی و تکراری را حذف می‌کند (ترتیب حفظ می‌شود)."""
        if value is None:
            return []
        cleaned: list[str] = []
        for item in value:
            text = str(item).strip() if item is not None else ""
            if text.endswith(".0") and text[:-2].isdigit():
                text = text[:-2]
            if text and text not in cleaned:
                cleaned.append(text)
        return cleaned


class OrgPreviewUnitOut(BaseModel):
    """یک واحد درخت منبع در پیش‌نمایش فیلتر واحد ریشه (POST /sites/{id}/mapping/org-preview)."""

    code: str
    name: str
    parent: str | None
    site_id: int | None  # سایتی که این واحد با قاعده‌ی نزدیک‌ترین ریشه به آن می‌رسد؛ None = بی‌سایت
    is_root: bool
    active_employees: int  # پرسنل فعال منبع که مستقیماً در همین واحدند


class OrgPreviewSiteOut(BaseModel):
    """خلاصه‌ی هر سایت هم‌منبع در پیش‌نمایش فیلتر واحد ریشه."""

    site_id: int
    site_name: str
    is_current: bool  # سایتی که تنظیماتش در حال ویرایش است
    roots: list[str]
    unit_count: int
    active_employee_count: int


class OrgPreviewOut(BaseModel):
    """خروجی پیش‌نمایش: واحدها، سایت‌ها، پرسنل بی‌سایت و خطای تنظیمات (در صورت وجود)."""

    units: list[OrgPreviewUnitOut]
    sites: list[OrgPreviewSiteOut]
    unassigned_active_employees: int
    error: str | None = None


class EmployeeMappingOut(EmployeeMappingIn):
    """خروجی نگاشت پرسنل ذخیره‌شده یک سایت."""

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
    # ستون شعبه تقویم (مثل BranchCode) - مقدار از «کد شعبه این سایت» در نگاشت پرسنل
    calendar_branch_column: str | None = None

    # ستون‌های تکمیلی تردد، لاگ تردد، کارکرد روزانه و شیفت‌ها (کلید «گروه.نقش»)
    # - هر بخش فقط اگر نگاشت شده باشد فعال است
    kara_schema: dict[str, str] = {}

    @field_validator("kara_schema", mode="before")
    @classmethod
    def _kara_schema(cls, value):
        """کلیدهای kara_schema را با فهرست مجاز ATTENDANCE_SCHEMA_DEFAULTS اعتبارسنجی و پاک‌سازی می‌کند."""
        return validate_schema(value, ATTENDANCE_SCHEMA_DEFAULTS)

    @model_validator(mode="after")
    def _validate_columns_for_mode(self) -> "AttendanceMappingIn":
        """بررسی می‌کند ستون‌های الزامیِ روش نگاشت انتخاب‌شده (mapping_mode) پر شده باشند؛ در غیر این صورت ValueError."""
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
    """خروجی نگاشت تردد ذخیره‌شده یک سایت."""

    id: int
    site_id: int

    @field_validator("kara_schema", mode="before")
    @classmethod
    def _kara_schema(cls, value):
        """مقدار ذخیره‌شده را بدون اعتبارسنجی مجدد به dict تبدیل می‌کند (None → {})."""
        return dict(value or {})

    model_config = ConfigDict(from_attributes=True)
