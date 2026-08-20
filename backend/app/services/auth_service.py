"""
منطق تجاری Authentication: بررسی نام‌کاربری/پسورد، صدور و تمدید توکن.
"""
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    validate_password_strength,
    verify_password,
    WeakPasswordError,
)
from app.models.employee import Department, Employee
from app.models.site import Site
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.core.ip_allowlist import is_ip_allowed, is_ip_allowlist_enforced
from app.core.rate_limit import check_login_lockout, record_failed_login, reset_login_attempts
from app.services.system_settings_service import SystemSettingsService
from app.schemas.user import UserOut


class AuthError(Exception):
    """خطای قابل نمایش به کاربر (نام‌کاربری اشتباه، توکن نامعتبر و ...)."""


class AuthLockedError(AuthError):
    """ورود به‌خاطر تلاش‌های ناموفق پیاپی موقتاً قفل شده — retry_after ثانیه باقی‌مانده تا باز شدن قفل است."""

    def __init__(self, retry_after_seconds: int):
        self.retry_after_seconds = retry_after_seconds
        minutes = retry_after_seconds // 60
        if minutes >= 1:
            human = f"{minutes} دقیقه"
        else:
            human = f"{retry_after_seconds} ثانیه"
        super().__init__(f"به‌خاطر تلاش‌های ناموفق پیاپی، ورود موقتاً قفل شده — {human} دیگر دوباره امتحان کنید.")


class AuthIpBlockedError(AuthError):
    """IP کاربر داخل رنج‌های مجاز ثبت‌شده در پنل Admin نیست — متن پیام از
    تنظیمات قابل‌تغییر از پنل خوانده می‌شود (نه یک متن ثابت در کد)."""

    def __init__(self, message: str):
        super().__init__(message)


class AuthService:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.repo = UserRepository(db)

    async def authenticate(self, username: str, password: str) -> User | None:
        """
        فقط تلاش برای ورود به‌عنوان کاربر مدیریتی (یوزرنیم/پسورد).
        برخلاف قبل، دیگر در صورت نبود تطبیق خطا نمی‌دهد (None برمی‌گرداند) —
        چون login() یکپارچه در ادامه باید بتواند به‌جایش کد پرسنلی/کد ملی
        پرسنل را هم امتحان کند.
        """
        user = await self.repo.get_by_username(username)
        if user is None or not verify_password(password, user.password_hash):
            return None
        if not user.is_active:
            raise AuthError("حساب کاربری غیرفعال است")

        user.last_login_at = datetime.now(timezone.utc)
        await self.db.commit()
        return user

    async def login(self, identifier: str, credential: str, client_ip: str | None = None) -> tuple[str, str]:
        """
        فرم ورود یکپارچه: همان دو فیلد، چه برای مدیریت و چه برای پرسنل.
        ابتدا به‌عنوان (یوزرنیم + رمز عبور) کاربر مدیریتی امتحان می‌شود؛
        اگر تطبیق نداشت، به‌عنوان (کد پرسنلی + کد ملی) پرسنل امتحان می‌شود.

        قبل از هر بررسی رمز عبوری، وضعیت قفل موقت (بعد از تلاش‌های ناموفق
        پیاپی روی همین identifier) چک می‌شود — اگر قفل باشد، حتی رمز درست
        هم پذیرفته نمی‌شود (تا شمارش تلاش‌های Brute-Force معنا داشته باشد).

        اگر رنج IP مجاز در پنل تعریف شده باشد، IP کاربر هم چک می‌شود — این
        بررسی قبل از هر چیز دیگری انجام می‌شود (حتی قبل از چک رمز)، چون اگر
        IP مجاز نیست، اصلاً نیازی به بررسی درست/غلط بودن رمز نیست.
        """
        if client_ip is not None and await is_ip_allowlist_enforced(self.db):
            if not await is_ip_allowed(self.db, client_ip):
                message = await SystemSettingsService(self.db).get_ip_blocked_message()
                raise AuthIpBlockedError(message)

        locked_remaining = await check_login_lockout(self.db, identifier)
        if locked_remaining is not None:
            raise AuthLockedError(retry_after_seconds=int(locked_remaining) + 1)

        user = await self.authenticate(identifier, credential)

        if user is None:
            employee = await self.repo.find_employee_for_login(identifier, credential)
            if employee is None:
                await record_failed_login(self.db, identifier)
                raise AuthError("اطلاعات ورود اشتباه است")
            user = await self.repo.get_or_create_employee_user(employee)

        await reset_login_attempts(self.db, identifier)
        access_token = create_access_token(subject=str(user.id))
        refresh_token = create_refresh_token(subject=str(user.id))
        return access_token, refresh_token

    async def refresh(self, refresh_token: str) -> tuple[str, str]:
        """
        تمدید Session — به‌صورت Sliding Window: هر بار که این متد صدا زده شود
        (یعنی کاربر در حال استفاده از برنامه است)، هم Access Token و هم یک
        Refresh Token تازه (با تاریخ انقضای جدید) صادر می‌شود. یعنی تا وقتی
        کاربر حداقل هر REFRESH_TOKEN_EXPIRE_DAYS یک‌بار برنامه را باز کند،
        هرگز به‌صورت خودکار Logout نمی‌شود — فقط با زدن دکمه «خروج» خارج می‌شود.
        """
        payload = decode_token(refresh_token)
        if payload is None or payload.get("type") != "refresh":
            raise AuthError("رفرش توکن نامعتبر یا منقضی‌شده است")

        user_id = payload.get("sub")
        user = await self.repo.get_by_id(int(user_id)) if user_id else None
        if user is None or not user.is_active:
            raise AuthError("کاربر یافت نشد یا غیرفعال است")

        access_token = create_access_token(subject=str(user.id))
        new_refresh_token = create_refresh_token(subject=str(user.id))
        return access_token, new_refresh_token

    async def verify_current_credential(self, user: User, current_password: str) -> None:
        """
        فقط بررسی می‌کند که «رمز عبور/کد ملی فعلی» درست وارد شده — بدون هیچ
        تغییری. هم توسط change_password (قبل از تنظیم رمز جدید) و هم برای
        تأیید هویت قبل از عملیات‌های حساس (مثل «تأیید و آپدیت» در پنل)
        استفاده می‌شود؛ چون Session به‌تنهایی (اگر دزدیده شود) نباید برای
        این‌جور عملیات کافی باشد.
        """
        if user.employee_id is None or user.has_custom_password:
            if not verify_password(current_password, user.password_hash):
                raise AuthError("رمز عبور فعلی اشتباه است")
        else:
            employee = await self.db.get(Employee, user.employee_id)
            if (
                employee is None
                or not employee.national_code
                or current_password.strip() != employee.national_code.strip()
            ):
                raise AuthError("رمز عبور فعلی وارد شده اشتباه است")

    async def change_password(self, user: User, current_password: str, new_password: str) -> None:
        """
        تغییر رمز عبور توسط خودِ کاربر.

        اگر کاربر هنوز رمز اختصاصی تعیین نکرده باشد (has_custom_password=False
        — یعنی همان پرسنلی که با کد ملی وارد می‌شود)، «رمز عبور فعلی» که از او
        خواسته می‌شود در واقع همان کد ملی خودش است (چون آن چیزی است که واقعاً
        می‌داند؛ password_hash فعلی یک مقدار تصادفی است که خودش نمی‌داند).
        بعد از این تغییر has_custom_password=True می‌شود و از این پس ورود با
        کد ملی دیگر کار نمی‌کند — طبق UserRepository.find_employee_for_login.

        کاربران مدیریتی (بدون employee_id، مثل Admin) همیشه از همان روش قبلی
        (بررسی رمز عبور فعلی) استفاده می‌کنند — آن‌ها اصلاً پرسنل نیستند که
        بخواهند به روش «کد ملی» وارد شوند.
        """
        await self.verify_current_credential(user, current_password)
        try:
            validate_password_strength(new_password)
        except WeakPasswordError as e:
            raise AuthError(str(e))

        user.password_hash = hash_password(new_password)
        user.has_custom_password = True
        user.must_change_password = False
        await self.db.commit()

    async def get_me(self, user: User) -> UserOut:
        """
        اطلاعات کاربر جاری را همراه با اطلاعات پرسنلی/سازمانی (در صورت وجود)
        برمی‌گرداند — برای نمایش نام و نام خانوادگی در AppBar و باکس اطلاعات
        شخصی/سازمانی بالای صفحه اطلاعیه‌ها. کاربران مدیریتی محض (بدون
        employee_id، مثل admin) فقط فیلدهای پایه را دارند.
        """
        base = UserOut.model_validate(user)
        permission_codes = await self.repo.get_permission_codes(user.id)
        base.can_clock_in_out = user.is_superuser or "attendance.clock_in_out" in permission_codes
        base.can_view_attendance_logs = user.is_superuser or "attendance.view_logs" in permission_codes
        base.can_view_clock_records = user.is_superuser or "attendance.view_clock_records" in permission_codes
        base.can_manage_birthday_messages = user.is_superuser or "hr.birthday_messages" in permission_codes
        # کد ملی هم خودش یک اعتبار ضعیف است (جاهای زیادی در دسترس است، قابل
        # تغییر/چرخش نیست) — پس هر پرسنلی که هنوز رمز اختصاصی تعیین نکرده
        # (همچنان با کد ملی وارد می‌شود)، صرف‌نظر از مقدار ذخیره‌شده در
        # دیتابیس، باید مجبور به تعیین یک رمز واقعی شود. این مقدار همیشه
        # محاسبه‌شده است، نه صرفاً یک فلگ ثابت — چون هیچ Migration ای برای
        # «همه پرسنلی که هنوز حساب کاربری نساخته‌اند» عملی نیست (حساب‌شان
        # فقط موقع اولین ورود واقعی خودکار ساخته می‌شود).
        if user.employee_id is not None and not user.has_custom_password:
            base.must_change_password = True
        if user.employee_id is None:
            return base

        result = await self.db.execute(
            select(Employee, Site.name, Department.name)
            .join(Site, Site.id == Employee.site_id)
            .outerjoin(Department, Department.id == Employee.department_id)
            .where(Employee.id == user.employee_id)
        )
        row = result.first()
        if row is None:
            return base

        employee, site_name, department_name = row
        base.employee_id = employee.id
        base.first_name = employee.first_name
        base.last_name = employee.last_name
        base.personnel_code = employee.personnel_code
        base.site_id = employee.site_id
        base.site_name = site_name
        base.department_id = employee.department_id
        base.department_name = department_name
        base.position_title = employee.position_title
        base.has_photo = bool(employee.photo_thumbnail)
        return base
