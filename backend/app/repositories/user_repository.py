"""
لایه‌ی دسترسی به داده برای User.
- خواندن کاربر با username یا id.
- محاسبه‌ی Permissionهای مؤثر کاربر (نقش‌های سراسری و محدود به سایت).
- پیدا کردن پرسنل برای ورود با کد پرسنلی + کد ملی و ساخت خودکار حساب کاربری متصل به پرسنل.
- فعال/غیرفعال‌سازی دستی پرسنل و تعیین/بازنشانی رمز عبور پرسنل توسط Admin.
"""
import secrets

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, normalize_login_credential, validate_password_strength
from app.core.site_access import all_site_ids, covers_all_sites
from app.models.employee import Employee
from app.models.user import Permission, Role, RolePermission, User, UserRole


class UserRepository:
    """عملیات پایگاه‌داده‌ای مربوط به کاربران، مجوزها و حساب‌های پرسنل؛ ورودی سازنده: نشست دیتابیس."""
    def __init__(self, db: AsyncSession):
        """نشست async دیتابیس را نگه می‌دارد."""
        self.db = db

    async def get_by_username(self, username: str) -> User | None:
        """کاربر با username داده‌شده را برمی‌گرداند؛ اگر نبود None."""
        result = await self.db.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: int) -> User | None:
        """کاربر با id داده‌شده را برمی‌گرداند؛ اگر نبود None."""
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_permission_codes(self, user_id: int, site_id: int | None = None) -> set[str]:
        """
        مجموعه‌ی کدهای Permission مؤثر کاربر: نقش‌های سراسری (site_id IS NULL) همیشه، و با site_id، نقش‌های همان سایت هم.
        بدون site_id (پرسش «در همه‌جا دارد؟»): مجوزهای نقش‌های سراسری به‌علاوه‌ی مجوزهایی که کاربر برای
        همه‌ی سایت‌های موجود دارد. برای پرسش «آیا کاربر اصلاً این قابلیت را دارد؟» (مثل فلگ‌های منوی get_me)
        از get_all_permission_codes استفاده کنید.
        """
        # کوئری: کدهای مجوز از مسیر UserRole -> Role -> RolePermission -> Permission
        stmt = (
            select(Permission.code)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .join(Role, Role.id == RolePermission.role_id)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user_id)
        )
        # فیلتر سایت: نقش‌های سراسری + (در صورت وجود) نقش‌های همان سایت
        if site_id is not None:
            stmt = stmt.where(or_(UserRole.site_id.is_(None), UserRole.site_id == site_id))
            result = await self.db.execute(stmt)
            return {row[0] for row in result.all()}

        # بدون site_id: سراسری‌ها + مجوزهایی که برای تک‌تک سایت‌های موجود داده شده‌اند
        result = await self.db.execute(stmt.add_columns(UserRole.site_id))
        codes: set[str] = set()
        sites_by_code: dict[str, set[int]] = {}
        for code, role_site_id in result.all():
            if role_site_id is None:
                codes.add(code)
            else:
                sites_by_code.setdefault(code, set()).add(role_site_id)
        if sites_by_code:
            every_site = await all_site_ids(self.db)
            codes |= {code for code, sites in sites_by_code.items() if covers_all_sites(sites, every_site)}
        return codes

    async def get_all_permission_codes(self, user_id: int) -> set[str]:
        """
        همه‌ی کدهای Permission کاربر از هر انتصاب نقش (سراسری یا سایت‌محور) بدون فیلتر سایت.
        فقط برای تصمیم‌های «آیا این قابلیت برای کاربر فعال است» (مثل فلگ‌های منوی get_me)؛
        برای محدود کردن داده به سایت‌ها از get_sites_with_permission استفاده شود.
        """
        # کوئری: کدهای مجوز از همه‌ی نقش‌های کاربر
        stmt = (
            select(Permission.code)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .join(Role, Role.id == RolePermission.role_id)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user_id)
        )
        result = await self.db.execute(stmt)
        return {row[0] for row in result.all()}

    # ---------- ورود پرسنل (کد پرسنلی + کد ملی) ----------

    async def find_employee_for_login(self, personnel_code: str, national_code: str) -> Employee | None:
        """
        پرسنل فعال (is_active از منبع و is_enabled دستی Admin) با کد پرسنلی و کد ملی مطابق را برمی‌گرداند؛ در تکرار بین سایت‌ها، اولین مورد.
        پرسنلی که رمز اختصاصی دارد (has_custom_password=True) با کد ملی پیدا نمی‌شود.
        ورودی‌ها با normalize_login_credential نرمال می‌شوند (ارقام فارسی/عربی به لاتین، حذف کاراکترهای نامرئی).
        """
        normalized_personnel_code = normalize_login_credential(personnel_code)
        normalized_national_code = normalize_login_credential(national_code)
        # کوئری: پرسنل مطابق که یا هنوز حساب کاربری ندارد یا حسابش رمز اختصاصی ندارد
        result = await self.db.execute(
            select(Employee)
            .outerjoin(User, User.employee_id == Employee.id)
            .where(
                Employee.personnel_code == normalized_personnel_code,
                Employee.national_code == normalized_national_code,
                Employee.is_active.is_(True),
                Employee.is_enabled.is_(True),
                or_(User.id.is_(None), User.has_custom_password.is_(False)),
            )
        )
        return result.scalars().first()

    async def get_or_create_employee_user(self, employee: Employee) -> User:
        """
        حساب User متصل به پرسنل (از طریق employee_id) را برمی‌گرداند و اگر نبود می‌سازد؛ حساب غیرفعال دوباره فعال می‌شود.
        username همان کد پرسنلی است (در تداخل بین سایت‌ها با پسوند site_id)؛
        password_hash یک مقدار تصادفی غیرقابل‌حدس است تا ورود از مسیر کد ملی انجام شود.
        """
        # اگر حساب از قبل وجود دارد، همان (پس از فعال‌سازی در صورت نیاز) برگردانده می‌شود
        result = await self.db.execute(select(User).where(User.employee_id == employee.id))
        user = result.scalar_one_or_none()
        if user is not None:
            if not user.is_active:
                user.is_active = True
                await self.db.commit()
            return user

        # انتخاب username یکتا
        username = employee.personnel_code
        existing_username = await self.db.execute(select(User).where(User.username == username))
        if existing_username.scalar_one_or_none() is not None:
            # تداخل نادر (مثلاً همین کد پرسنلی در Site دیگری هم به یوزرنیم تبدیل شده)
            username = f"{employee.personnel_code}-{employee.site_id}"

        # ساخت حساب جدید با رمز تصادفی
        random_password = secrets.token_urlsafe(32)
        user = User(
            username=username,
            password_hash=hash_password(random_password),
            employee_id=employee.id,
            is_active=True,
            is_superuser=False,
        )
        self.db.add(user)
        await self.db.commit()
        await self.db.refresh(user)
        return user

    # ---------- فعال/غیرفعال‌کردن دستی توسط Admin (مستقل از Sync Engine) ----------

    async def set_employee_enabled(self, employee: Employee, enabled: bool) -> Employee:
        """
        فلگ is_enabled پرسنل را تنظیم می‌کند (مستقل از is_active که Sync Engine کنترل می‌کند و با Sync بازنویسی نمی‌شود).
        اگر پرسنل حساب User داشته باشد، User.is_active هم هماهنگ می‌شود تا روی هر دو روش ورود و نشست‌های باز اثر کند؛
        حساب جدیدی ساخته نمی‌شود. خروجی: پرسنل به‌روزشده.
        """
        employee.is_enabled = enabled
        # هماهنگ‌سازی وضعیت حساب کاربری متصل (در صورت وجود)
        result = await self.db.execute(select(User).where(User.employee_id == employee.id))
        user = result.scalar_one_or_none()
        if user is not None:
            user.is_active = enabled
        await self.db.commit()
        await self.db.refresh(employee)
        return employee

    # ---------- تنظیم/بازنشانی دستی رمز عبور توسط Admin ----------

    async def set_employee_password(self, employee: Employee, new_password: str) -> User:
        """
        Admin برای پرسنل رمز مشخص تعیین می‌کند؛ از این پس ورود با «کد پرسنلی (username) + این رمز» است و ورود با کد ملی غیرفعال می‌شود.
        must_change_password=True می‌شود تا پرسنل پس از اولین ورود رمز شخصی خود را تعیین کند.
        خروجی: حساب User پرسنل. اگر رمز ضعیف باشد validate_password_strength خطا می‌دهد.
        """
        validate_password_strength(new_password)
        user = await self.get_or_create_employee_user(employee)
        user.password_hash = hash_password(new_password)
        user.has_custom_password = True
        user.must_change_password = True
        await self.db.commit()
        return user

    async def reset_employee_to_default_login(self, employee: Employee) -> User:
        """
        پرسنل را به روش ورود پیش‌فرض (کد پرسنلی + کد ملی) برمی‌گرداند؛ رمز اختصاصی قبلی
        با یک رمز تصادفی غیرقابل‌حدس جایگزین می‌شود. خروجی: حساب User پرسنل.
        """
        user = await self.get_or_create_employee_user(employee)
        user.password_hash = hash_password(secrets.token_urlsafe(32))
        user.has_custom_password = False
        await self.db.commit()
        return user
