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
    can_clock_in_out: bool = False  # آیا مجوز آزمایشی «ثبت ورود/خروج مبتنی بر GPS» را دارد
    can_view_attendance_logs: bool = False  # آیا مجوز مشاهده گزارش «پرسنل آنلاین» (Session زنده) را دارد
    can_view_clock_records: bool = False  # آیا مجوز مشاهده گزارش ورود/خروج آزمایشی همه پرسنل را دارد
    can_manage_clock_records: bool = False  # آیا مجوز افزودن/ویرایش/حذف دستی رکورد ورود/خروج را دارد
    can_view_site_notice_report: bool = False  # آیا site_manager سایتی است (برای «گزارش اطلاعیه‌های سایت من»)
    can_manage_birthday_messages: bool = False  # آیا مجوز مدیریت پیام‌های تبریک تولد را دارد

    model_config = ConfigDict(from_attributes=True)
