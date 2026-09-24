"""
Schema های Pydantic پرسنل: خروجی پرسنل و صفحه‌بندی، ورودی «افزودن دستی پرسنل»،
کارت «متولدین امروز» و ری‌اکشن تبریک، و ورودی‌های تغییر وضعیت/رمز/نمایش تولد.
"""
from pydantic import BaseModel, ConfigDict, Field


class EmployeeOut(BaseModel):
    """خروجی یک پرسنل در Endpoint های /employees (فهرست، ایجاد و ویرایش)."""

    id: int
    personnel_code: str
    national_code: str | None
    first_name: str
    last_name: str
    mobile: str | None
    site_id: int
    department_id: int | None
    position_title: str | None = None
    is_active: bool  # وضعیت در منبع (فقط توسط Sync Engine تعیین می‌شود؛ غیرقابل‌ویرایش دستی)
    is_enabled: bool  # تصمیم دستی Admin — کاملاً مستقل از Sync، با آن بازنویسی نمی‌شود
    has_custom_password: bool = False  # آیا رمز عبور اختصاصی دارد (یعنی دیگر با کد ملی وارد نمی‌شود)
    # این دو فیلد را فقط GET /employees (با Join روی Site/Department) پر می‌کند؛ Endpoint های دیگر
    # (مثل PATCH) خالی می‌گذارند و فرانت‌اند نام سایت/واحد را از فهرست محلی خودش پیدا می‌کند.
    site_name: str | None = None
    department_name: str | None = None
    is_manually_created: bool = False  # آیا از طریق «افزودن دستی پرسنل» ثبت شده (نه Sync)

    model_config = ConfigDict(from_attributes=True)


class EmployeeCreateIn(BaseModel):
    """ورودی «افزودن دستی پرسنل» — فقط زمانی که یک نفر واقعاً در هیچ منبع Sync موجود نیست."""

    personnel_code: str = Field(min_length=1, max_length=64)
    first_name: str = Field(min_length=1, max_length=128)
    last_name: str = Field(min_length=1, max_length=128)
    site_id: int
    national_code: str | None = Field(default=None, max_length=32)
    mobile: str | None = Field(default=None, max_length=32)
    department_id: int | None = None
    position_title: str | None = Field(default=None, max_length=128)


class EmployeePageOut(BaseModel):
    """یک صفحه از لیست پرسنل — برای Pagination سمت سرور (به‌جای واکشی صدها/هزاران
    ردیف در یک درخواست)."""

    items: list[EmployeeOut]
    total: int


class BirthdayReactorOut(BaseModel):
    """یک نفر که تبریک گفته - نام، واحد سازمانی و آواتار، برای فهرست بازشونده."""

    user_id: int
    employee_id: int | None = None
    name: str
    department: str | None = None
    emoji: str
    # فرانت‌اند فقط وقتی True است درخواست تصویر می‌زند تا برای افراد بدون عکس درخواست ۴۰۴ ارسال نشود
    has_photo: bool = False


class BirthdayEmployeeOut(BaseModel):
    """یک پرسنل متولد امروز (شمسی) — برای کارت «متولدین روز جاری» در داشبورد."""

    id: int
    first_name: str
    last_name: str
    site_name: str | None = None
    department_name: str | None = None
    # ری‌اکشن‌های تبریک همیشه برگردانده می‌شوند؛ فهرست تبریک‌گویندگان برای همه قابل‌مشاهده است
    reaction_counts: dict[str, int] = {}  # تعداد هر ایموجی
    reactors: list[BirthdayReactorOut] = []
    my_reaction: str | None = None  # ایموجی ثبت‌شده توسط کاربر جاری (در صورت وجود)
    # آیا کاربر جاری خودش همین متولد است؟ (نباید بتواند ری‌اکشن بزند)
    is_self: bool = False
    has_photo: bool = False


class SetBirthdayReactionIn(BaseModel):
    """ورودی ثبت ری‌اکشن (ایموجی) تبریک تولد روی یک پرسنل متولد امروز."""

    emoji: str


class EmployeeEnabledUpdate(BaseModel):
    """فعال/غیرفعال‌کردن دستی یک پرسنل از پنل Admin — مستقل از is_active که توسط Sync Engine کنترل می‌شود."""
    is_enabled: bool


class EmployeePasswordSet(BaseModel):
    """برای تعیین دستی رمز عبور ورود یک پرسنل توسط Admin (بعد از این، ورود با کد ملی دیگر کار نمی‌کند)."""
    new_password: str = Field(min_length=6, description="حداقل ۶ کاراکتر")


class BirthdayVisibilityUpdate(BaseModel):
    """تنظیم شخصی/خودانتخاب هر پرسنل — آیا روز تولدش در داشبورد همکاران دیده شود یا نه."""
    hide_birthday_in_dashboard: bool
