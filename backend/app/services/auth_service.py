"""
منطق تجاری احراز هویت (AuthService).
- ورود یکپارچه (مدیریت با یوزرنیم/رمز، پرسنل با کد پرسنلی/کد ملی یا رمز اختصاصی) با بررسی IP مجاز و قفل موقت.
- صدور و تمدید توکن‌ها، بررسی اعتبار فعلی و تغییر رمز توسط کاربر.
- ساخت پاسخ /auth/me شامل اطلاعات پرسنلی و فلگ‌های مجوز منوها.
"""
from datetime import datetime, timezone
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    normalize_login_credential,
    validate_password_strength,
    verify_password,
    WeakPasswordError,
)
from app.models.employee import Department, Employee
from app.models.site import AttendanceMapping, Site
from app.models.leave_request import LeaveRequestMapping
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.core.ip_allowlist import is_ip_allowed, is_ip_allowlist_enforced
from app.core.rate_limit import check_login_lockout, record_failed_login, reset_login_attempts
from app.core.site_access import get_sites_with_permission
from app.services.system_settings_service import SystemSettingsService
from app.schemas.user import UserOut

logger = logging.getLogger("faipco.auth")


class AuthError(Exception):
    """خطای قابل نمایش به کاربر (نام‌کاربری اشتباه، توکن نامعتبر و ...)."""


class AuthLockedError(AuthError):
    """ورود به‌خاطر تلاش‌های ناموفق پیاپی موقتاً قفل شده — retry_after ثانیه باقی‌مانده تا باز شدن قفل است."""

    def __init__(self, retry_after_seconds: int):
        """ورودی: ثانیه‌های باقی‌مانده تا باز شدن قفل؛ پیام فارسی با واحد دقیقه یا ثانیه ساخته می‌شود."""
        self.retry_after_seconds = retry_after_seconds
        minutes = retry_after_seconds // 60  # نمایش به دقیقه اگر حداقل یک دقیقه باقی باشد
        if minutes >= 1:
            human = f"{minutes} دقیقه"
        else:
            human = f"{retry_after_seconds} ثانیه"
        super().__init__(f"به‌خاطر تلاش‌های ناموفق پیاپی، ورود موقتاً قفل شده — {human} دیگر دوباره امتحان کنید.")


class AuthIpBlockedError(AuthError):
    """IP کاربر داخل رنج‌های مجاز ثبت‌شده در پنل Admin نیست — متن پیام از
    تنظیمات قابل‌تغییر از پنل خوانده می‌شود (نه یک متن ثابت در کد)."""

    def __init__(self, message: str):
        """ورودی: متن پیام قابل‌تنظیم از پنل."""
        super().__init__(message)


class AuthService:
    """سرویس احراز هویت و اطلاعات کاربر جاری؛ ورودی سازنده: نشست دیتابیس."""
    def __init__(self, db: AsyncSession):
        """نشست دیتابیس و UserRepository را نگه می‌دارد."""
        self.db = db
        self.repo = UserRepository(db)

    async def authenticate(self, username: str, password: str) -> User | None:
        """
        ورود با یوزرنیم/رمز (کاربر مدیریتی یا پرسنل دارای رمز اختصاصی) را امتحان می‌کند.
        خروجی: User در صورت تطبیق (و ثبت last_login_at)، وگرنه None تا login() روش کد پرسنلی/کد ملی را امتحان کند.
        خطا: AuthError اگر رمز درست ولی حساب غیرفعال باشد.
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
        ورود یکپارچه؛ ورودی: شناسه (یوزرنیم/کد پرسنلی)، اعتبار (رمز/کد ملی) و IP کلاینت. خروجی: (access_token, refresh_token).
        ترتیب: بررسی IP مجاز (AuthIpBlockedError) ← قفل موقت این شناسه (AuthLockedError، حتی با رمز درست)
        ← یوزرنیم/رمز ← کد پرسنلی/کد ملی؛ در شکست، تلاش ناموفق ثبت و AuthError داده می‌شود.
        """
        # بررسی IP فقط وقتی فهرست IP مجاز در پنل تعریف شده باشد
        if client_ip is not None and await is_ip_allowlist_enforced(self.db):
            if not await is_ip_allowed(self.db, client_ip):
                message = await SystemSettingsService(self.db).get_ip_blocked_message()
                raise AuthIpBlockedError(message)

        # قفل موقت پس از تلاش‌های ناموفق پیاپی روی همین شناسه
        locked_remaining = await check_login_lockout(self.db, identifier)
        if locked_remaining is not None:
            raise AuthLockedError(retry_after_seconds=int(locked_remaining) + 1)

        user = await self.authenticate(identifier, credential)

        # اگر یوزرنیم/رمز تطبیق نداشت، ورود پرسنل با کد پرسنلی + کد ملی امتحان می‌شود
        if user is None:
            employee = await self.repo.find_employee_for_login(identifier, credential)
            if employee is None:
                await record_failed_login(self.db, identifier)
                # لاگ تشخیصی بدون ذخیره‌ی خودِ کد ملی/رمز (PII): فقط طول ورودی و اینکه آیا نرمال‌سازی
                # (ارقام فارسی/عربی یا کاراکتر نامرئی) مقدار را تغییر داده است
                normalized = normalize_login_credential(credential)
                logger.info(
                    "ورود پرسنل ناموفق — identifier=%s، طول ورودی=%d، "
                    "نرمال‌سازی مقدار را تغییر داد=%s (یعنی رقم فارسی/عربی یا "
                    "کاراکتر نامرئی در ورودی بوده)",
                    identifier,
                    len(credential),
                    credential.strip() != normalized,
                )
                raise AuthError("اطلاعات ورود اشتباه است")
            user = await self.repo.get_or_create_employee_user(employee)  # حساب پرسنل در اولین ورود ساخته می‌شود

        await reset_login_attempts(self.db, identifier)  # ورود موفق: شمارنده‌ی تلاش‌ها صفر می‌شود
        access_token = create_access_token(subject=str(user.id))
        refresh_token = create_refresh_token(subject=str(user.id))
        return access_token, refresh_token

    async def refresh(self, refresh_token: str) -> tuple[str, str]:
        """
        تمدید نشست به‌صورت Sliding Window؛ ورودی: refresh token، خروجی: access token و refresh token تازه (با انقضای جدید).
        تا وقتی کاربر حداقل هر REFRESH_TOKEN_EXPIRE_DAYS یک‌بار برنامه را باز کند، خودکار خارج نمی‌شود.
        خطا: AuthError برای توکن نامعتبر/منقضی یا کاربر ناموجود/غیرفعال.
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
        بدون تغییر چیزی، درستی «رمز عبور/کد ملی فعلی» کاربر را بررسی می‌کند؛ در صورت نادرستی AuthError می‌دهد.
        در change_password و برای تأیید هویت پیش از عملیات حساس (مثل «تأیید و آپدیت») استفاده می‌شود،
        تا نشست دزدیده‌شده به‌تنهایی کافی نباشد.
        """
        # کاربر مدیریتی یا پرسنل دارای رمز اختصاصی: بررسی رمز؛ پرسنل بدون رمز اختصاصی: مقایسه با کد ملی
        if user.employee_id is None or user.has_custom_password:
            if not verify_password(current_password, user.password_hash):
                raise AuthError("رمز عبور فعلی اشتباه است")
        else:
            employee = await self.db.get(Employee, user.employee_id)
            if (
                employee is None
                or not employee.national_code
                or normalize_login_credential(current_password) != normalize_login_credential(employee.national_code)
            ):
                raise AuthError("رمز عبور فعلی وارد شده اشتباه است")

    async def change_password(self, user: User, current_password: str, new_password: str) -> None:
        """
        تغییر رمز توسط خودِ کاربر؛ ورودی: کاربر، رمز فعلی (برای پرسنل بدون رمز اختصاصی = کد ملی) و رمز جدید.
        رمز جدید باید قانون قدرت رمز را رعایت کند (وگرنه AuthError). پس از تغییر has_custom_password=True
        و must_change_password=False می‌شود و ورود با کد ملی دیگر ممکن نیست.
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
        ورودی: کاربر جاری. خروجی: UserOut با فلگ‌های مجوز منوها و (در صورت اتصال به پرسنل) اطلاعات پرسنلی/سازمانی
        برای AppBar و باکس اطلاعات بالای صفحه‌ی اطلاعیه‌ها. کاربران مدیریتی بدون employee_id فقط فیلدهای پایه و فلگ‌ها را دارند.
        """
        base = UserOut.model_validate(user)
        # مجوزها از همه‌ی نقش‌ها (سراسری و سایت‌محور) خوانده می‌شوند، چون این فلگ‌ها فقط تعیین می‌کنند
        # کدام منو دیده شود، نه محدودسازی داده به یک سایت
        permission_codes = await self.repo.get_all_permission_codes(user.id)
        base.can_clock_in_out = user.is_superuser or "attendance.clock_in_out" in permission_codes
        base.can_view_attendance_logs = user.is_superuser or "attendance.view_logs" in permission_codes
        base.can_view_clock_records = user.is_superuser or "attendance.view_clock_records" in permission_codes
        base.can_manage_clock_records = user.is_superuser or "attendance.manage_clock_records" in permission_codes
        base.can_manage_birthday_messages = user.is_superuser or "hr.birthday_messages" in permission_codes
        base.can_manage_performance_structure = (
            user.is_superuser or "performance.structure.manage" in permission_codes
        )
        base.can_manage_performance_periods = user.is_superuser or "performance.periods.manage" in permission_codes
        base.can_manage_performance_forms = user.is_superuser or "performance.forms.manage" in permission_codes
        base.can_manage_performance_assignments = (
            user.is_superuser or "performance.assignments.manage" in permission_codes
        )
        base.can_view_performance_reports = user.is_superuser or "performance.reports.view" in permission_codes
        # منوی مرخصی/ماموریت با مجوز سراسری leave_requests.view یا هر مجوز به‌تفکیک نوع
        # (leave_requests.view.type.<id>، مثل نقش «حراست») نمایش داده می‌شود
        base.can_view_leave_requests = (
            user.is_superuser
            or "leave_requests.view" in permission_codes
            or any(code.startswith("leave_requests.view.type.") for code in permission_codes)
        )
        base.can_manage_leave_requests = user.is_superuser or "leave_requests.manage" in permission_codes
        # «محدود به نوع»: فقط مجوز به‌تفکیک نوع دارد و هیچ‌یک از دو مجوز سراسری را ندارد
        # (همان تشخیص _get_view_access سمت سرور)
        base.leave_requests_type_restricted = (
            not user.is_superuser
            and "leave_requests.view" not in permission_codes
            and "leave_requests.manage" not in permission_codes
            and any(code.startswith("leave_requests.view.type.") for code in permission_codes)
        )
        base.can_view_vehicles_report = user.is_superuser or "vehicles.view_all" in permission_codes
        base.can_manage_sites = user.is_superuser or "sites.manage" in permission_codes
        # sites.manage شامل مشاهده هم هست
        base.can_view_sites = base.can_manage_sites or "sites.view" in permission_codes
        base.can_manage_sync = user.is_superuser or "sync.manage" in permission_codes
        base.can_manage_users = user.is_superuser or "users.manage" in permission_codes
        base.can_manage_roles = user.is_superuser or "roles.manage" in permission_codes
        base.can_manage_ip_allowlist = user.is_superuser or "system.ip_allowlist" in permission_codes
        base.can_view_feedback = (
            user.is_superuser or "feedback.view" in permission_codes or "feedback.view_all" in permission_codes
        )
        base.can_manage_backup = user.is_superuser or "system.backup" in permission_codes
        base.can_view_employees = user.is_superuser or "employees.view" in permission_codes
        base.can_update_employees = user.is_superuser or "employees.update" in permission_codes
        base.can_create_employees = user.is_superuser or "employees.create" in permission_codes
        base.can_manage_vehicles = user.is_superuser or "vehicles.manage" in permission_codes
        base.can_view_insurance = (
            user.is_superuser or "insurance.view" in permission_codes or "insurance.manage" in permission_codes
        )
        base.can_manage_insurance = user.is_superuser or "insurance.manage" in permission_codes
        # ماژول بیمه تکمیلی سراسری است (نه به‌ازای سایت)؛ خواندن سبک از تنظیمات
        try:
            from app.services.insurance_service import InsuranceService

            base.insurance_disabled = not (await InsuranceService(self.db).get_settings())["enabled"]
        except Exception:  # noqa: BLE001 - نباید ورود را خراب کند
            base.insurance_disabled = False
        base.can_view_sync = user.is_superuser or "sync.view" in permission_codes
        base.can_run_sync = user.is_superuser or "sync.run" in permission_codes
        base.can_bust_cache = user.is_superuser or "system.cache_bust" in permission_codes
        base.can_manage_system_settings = user.is_superuser or "system.settings" in permission_codes
        # گزارش اطلاعیه‌های سایت: هر نقشی که مجوز notices.site_report را حداقل برای یک سایت داشته باشد
        # (این مجوز به‌طور پیش‌فرض در Migration 035 به site_manager داده شده)؛ None یعنی همه‌ی سایت‌ها
        site_notice_report_sites = await get_sites_with_permission(self.db, user, "notices.site_report")
        base.can_view_site_notice_report = user.is_superuser or bool(
            site_notice_report_sites is None or len(site_notice_report_sites) > 0
        )
        # کد ملی اعتبار ضعیفی است (در دسترس و غیرقابل‌تغییر)، پس پرسنلی که هنوز رمز اختصاصی ندارد
        # همیشه ملزم به تعیین رمز می‌شود؛ این مقدار در لحظه محاسبه می‌شود، مستقل از مقدار ذخیره‌شده در دیتابیس
        # (حساب پرسنل تا اولین ورود ساخته نمی‌شود، پس با migration قابل تنظیم نیست)
        if user.employee_id is not None and not user.has_custom_password:
            base.must_change_password = True
        if user.employee_id is None:
            return base

        # کوئری: پرسنل متصل همراه با نام سایت، نام واحد، نگاشت تردد و وضعیت ماژول مرخصی سایت
        result = await self.db.execute(
            select(Employee, Site.name, Department.name, AttendanceMapping.id, LeaveRequestMapping.is_disabled)
            .join(Site, Site.id == Employee.site_id)
            .outerjoin(Department, Department.id == Employee.department_id)
            .outerjoin(AttendanceMapping, AttendanceMapping.site_id == Site.id)
            .outerjoin(LeaveRequestMapping, LeaveRequestMapping.site_id == Site.id)
            .where(Employee.id == user.employee_id)
        )
        row = result.first()
        if row is None:
            return base

        employee, site_name, department_name, attendance_mapping_id, leave_module_disabled = row
        base.employee_id = employee.id
        base.first_name = employee.first_name
        base.last_name = employee.last_name
        base.personnel_code = employee.personnel_code
        base.site_id = employee.site_id
        base.site_name = site_name
        base.department_id = employee.department_id
        base.department_name = department_name
        base.position_title = employee.position_title
        # اولویت با ایمیل Employee (همان الگوی password_reset_service.py)؛ User.email معمولاً فقط
        # برای کاربران بدون Employee مقدار دارد
        base.email = employee.email or user.email
        base.mobile = employee.mobile
        base.has_photo = bool(employee.photo_thumbnail)
        base.hide_birthday_in_dashboard = employee.hide_birthday_in_dashboard
        # قابلیت سطح سایت (نه Permission؛ برای همه‌ی پرسنل): فقط اگر سایت پرسنل AttendanceMapping
        # (نگاشت جدول/ستون تردد دستگاهی) داشته باشد True است؛ وگرنه کارت‌های داشبورد «به‌زودی» نشان می‌دهند
        base.has_monthly_attendance = attendance_mapping_id is not None
        # اگر ماژول مرخصی/ماموریت برای سایت پرسنل از پنل غیرفعال شده باشد، صفحه‌ی درخواست بسته
        # و کارت داشبورد «غیرفعال» نمایش داده می‌شود
        base.leave_requests_disabled = bool(leave_module_disabled)
        return base
