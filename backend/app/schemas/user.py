"""Schema های Pydantic مربوط به User."""
from pydantic import BaseModel, ConfigDict


class UserOut(BaseModel):
    id: int
    username: str
    email: str | None
    is_active: bool
    is_superuser: bool
    has_custom_password: bool
    must_change_password: bool

    # اطلاعات پرسنلی/سازمانی — فقط اگر این حساب به یک رکورد Employee سینک‌شده
    # وصل باشد (User.employee_id). کاربران مدیریتی محض (مثل admin) همه این
    # فیلدها را None دریافت می‌کنند؛ فرانت‌اند باید با این حالت کنار بیاید.
    employee_id: int | None = None
    first_name: str | None = None
    last_name: str | None = None
    personnel_code: str | None = None
    site_id: int | None = None
    site_name: str | None = None
    department_id: int | None = None
    department_name: str | None = None
    position_title: str | None = None
    has_photo: bool = False
    hide_birthday_in_dashboard: bool = False
    can_clock_in_out: bool = False  # آیا مجوز آزمایشی «ثبت ورود/خروج مبتنی بر GPS» را دارد
    has_kara_workflow: bool = False  # آیا سایت خودِ این پرسنل به «کاراوب» وصل است (گزارش تردد ماهانه)
    can_view_attendance_logs: bool = False  # آیا مجوز مشاهده گزارش «پرسنل آنلاین» (Session زنده) را دارد
    can_view_clock_records: bool = False  # آیا مجوز مشاهده گزارش ورود/خروج آزمایشی همه پرسنل را دارد
    can_manage_clock_records: bool = False  # آیا مجوز افزودن/ویرایش/حذف دستی رکورد ورود/خروج را دارد
    can_view_site_notice_report: bool = False  # آیا site_manager سایتی است (برای «گزارش اطلاعیه‌های سایت من»)
    can_view_vehicles_report: bool = False  # آیا Admin یا نقش «حراست» است (برای «گزارش خودروهای پرسنل»)
    # ⚠️ طبق درخواست صریح: هر مجوزی که به یک نقش داده شود، منوی متناظرش هم
    # باید در پنل کاربری اضافه شود — نه فقط برای Admin واقعی کار کند.
    # صفحات زیر قبلاً فقط با is_superuser محافظت می‌شدند (AdminRoute)؛
    # حالا اگر یک نقش غیر-Admin هم مجوز متناظر را داشته باشد، منویشان
    # نمایش داده می‌شود.
    can_manage_sites: bool = False  # sites.manage — «سایت‌ها» و «واحدهای سازمانی»
    can_view_sites: bool = False  # sites.view (یا sites.manage) — مشاهده فقط‌خواندنی «سایت‌ها»
    can_manage_sync: bool = False  # sync.manage — «همگام‌سازی دیتابیس»
    can_manage_users: bool = False  # users.manage — «مدیریت دسترسی» و «انتصاب دسته‌جمعی نقش»
    can_manage_roles: bool = False  # roles.manage — «مدیریت نقش/مجوز»
    can_manage_ip_allowlist: bool = False  # system.ip_allowlist — «رنج‌های IP مجاز»
    can_manage_backup: bool = False  # system.backup — «پشتیبان‌گیری»
    # ⚠️ فلگ‌های تازه‌کشف‌شده: این مجوزها از قبل در Backend واقعاً چک
    # می‌شدند (require_permission/get_sites_with_permission)، ولی هیچ
    # فلگ متناظری اینجا نداشتند — یعنی حتی اگر یک نقش این مجوز را داشت،
    # هیچ منو/مسیری در Frontend برایش باز نمی‌شد. طبق بازخورد صریح («هر
    # مجوزی که به یک نقش بدهم باید منویش هم اضافه شود»).
    can_view_employees: bool = False  # employees.view — «پرسنل»
    can_update_employees: bool = False  # employees.update — ویرایش اطلاعات پرسنل
    can_create_employees: bool = False  # employees.create — افزودن دستی پرسنل
    can_manage_vehicles: bool = False  # vehicles.manage — ویرایش/حذف خودروی هر پرسنلی
    can_view_sync: bool = False  # sync.view — مشاهده وضعیت همگام‌سازی (فقط‌خواندنی)
    can_run_sync: bool = False  # sync.run — اجرای همگام‌سازی یک سایت
    can_bust_cache: bool = False  # system.cache_bust — پاک‌سازی Cache سرور
    can_manage_system_settings: bool = False  # system.settings — «تنظیمات سامانه» (مثل عکس پس‌زمینه ورود)
    can_manage_birthday_messages: bool = False  # آیا مجوز مدیریت پیام‌های تبریک تولد را دارد

    model_config = ConfigDict(from_attributes=True)
