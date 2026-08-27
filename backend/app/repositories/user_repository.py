"""
لایه دسترسی به داده برای User.
محاسبه Permission های مؤثر کاربر (با در نظر گرفتن نقش‌های سراسری و Site-scoped) اینجا انجام می‌شود.
همچنین منطق «پیدا کردن پرسنل برای ورود» و «ساخت خودکار حساب کاربری متصل به پرسنل» اینجاست.
"""
import secrets

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password, normalize_login_credential, validate_password_strength
from app.models.employee import Employee
from app.models.user import Permission, Role, RolePermission, User, UserRole


class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_username(self, username: str) -> User | None:
        result = await self.db.execute(select(User).where(User.username == username))
        return result.scalar_one_or_none()

    async def get_by_id(self, user_id: int) -> User | None:
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalar_one_or_none()

    async def get_permission_codes(self, user_id: int, site_id: int | None = None) -> set[str]:
        """
        فهرست کدهای Permission مؤثر برای کاربر را برمی‌گرداند.

        نقش‌های سراسری (UserRole.site_id IS NULL) همیشه لحاظ می‌شوند.
        اگر site_id پاس داده شود، نقش‌های مخصوص همان Site هم اضافه می‌شوند
        (مثلاً کاربری که فقط نقش "HR سایت ۲" را دارد، فقط وقتی site_id=2 چک شود این مجوز را دارد).

        ⚠️ اگر site_id داده نشود، فقط نقش‌های سراسری دیده می‌شوند — نقش‌های
        سایت‌محور این کاربر (که بعد از اجباری‌شدن site_id در انتصاب نقش،
        امروز اکثریت قریب‌به‌اتفاق انتصاب‌ها همین‌طورند) اصلاً لحاظ نمی‌شوند.
        برای «آیا این کاربر اصلاً این قابلیت را دارد؟» (مثلاً برای فلگ‌های
        get_me که تعیین می‌کنند کدام منو نمایش داده شود، نه محدودسازی داده
        به یک سایت خاص) به‌جای این تابع از get_all_permission_codes پایین
        استفاده کنید.
        """
        stmt = (
            select(Permission.code)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .join(Role, Role.id == RolePermission.role_id)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user_id)
        )
        if site_id is not None:
            stmt = stmt.where(or_(UserRole.site_id.is_(None), UserRole.site_id == site_id))
        else:
            stmt = stmt.where(UserRole.site_id.is_(None))

        result = await self.db.execute(stmt)
        return {row[0] for row in result.all()}

    async def get_all_permission_codes(self, user_id: int) -> set[str]:
        """
        همه کدهای Permission این کاربر — از هر انتصاب نقشی، چه سراسری چه
        محدود به یک سایت خاص، بدون هیچ فیلتر سایتی. ⚠️ فقط برای تصمیمات
        سطح «آیا این قابلیت اصلاً برای این کاربر فعال است» (مثل فلگ‌های
        get_me که منوها را کنترل می‌کنند) مناسب است — هرگز برای محدودسازی
        داده به یک سایت مشخص استفاده نشود؛ برای آن منظور همیشه
        get_sites_with_permission (که خودِ سایت‌های مجاز را برمی‌گرداند،
        نه فقط بله/خیر) درست‌تر است.
        """
        stmt = (
            select(Permission.code)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .join(Role, Role.id == RolePermission.role_id)
            .join(UserRole, UserRole.role_id == Role.id)
            .where(UserRole.user_id == user_id)
        )
        result = await self.db.execute(stmt)
        return {row[0] for row in result.all()}

    async def get_managed_site_ids(self, user_id: int, role_name: str) -> list[int]:
        """
        شناسه‌های Site هایی که این کاربر برایشان نقش role_name را با site_id
        مشخص دارد (مثلاً «مدیر کدام سایت‌هاست؟») — برای گزارش‌هایی که به یک
        Site خاص محدود می‌شوند (مثل «گزارش اطلاعیه‌های سایت من»)، نه یک
        Permission ساده. اگر کاربر این نقش را سراسری (بدون site_id) داشته
        باشد، نادیده گرفته می‌شود — این متد فقط انتصاب‌های Site-scoped را
        برمی‌گرداند.
        """
        stmt = (
            select(UserRole.site_id)
            .join(Role, Role.id == UserRole.role_id)
            .where(UserRole.user_id == user_id, Role.name == role_name, UserRole.site_id.is_not(None))
        )
        result = await self.db.execute(stmt)
        return [row[0] for row in result.all()]

    # ---------- ورود پرسنل (کد پرسنلی + کد ملی) ----------

    async def find_employee_for_login(self, personnel_code: str, national_code: str) -> Employee | None:
        """
        پرسنل فعالی (هم is_active از منبع، هم is_enabled دستی Admin) که هم کد
        پرسنلی و هم کد ملی‌اش دقیقاً مطابقت داشته باشد را برمی‌گرداند.
        اگر (به‌ندرت) بین سایت‌های مختلف کد پرسنلی تکراری باشد، اولین مورد فعال برگردانده می‌شود.

        نکته مهم: اگر این پرسنل قبلاً رمز عبور اختصاصی تعیین کرده باشد
        (User.has_custom_password=True)، ورود با کد ملی دیگر برایش کار
        نمی‌کند — باید حتماً از رمز عبور جدیدش استفاده کند.

        ورودی‌ها قبل از مقایسه با normalize_login_credential نرمال‌سازی
        می‌شوند (ارقام فارسی/عربی→لاتین، حذف کاراکترهای نامرئی) — رفع یک
        مشکل واقعی: پرسنلی که از کیبورد فارسی موبایل استفاده می‌کرد، با
        تایپ کاملاً درست کد ملی‌اش «اطلاعات ورود اشتباه است» می‌گرفت.
        """
        normalized_personnel_code = normalize_login_credential(personnel_code)
        normalized_national_code = normalize_login_credential(national_code)
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
        هر پرسنل یک حساب User مرتبط (از طریق employee_id) دارد که اولین بار
        هنگام ورود موفق یا اختصاص نقش، به‌صورت خودکار ساخته می‌شود. Username
        همان کد پرسنلی خودش است (چیز جدیدی ساخته نمی‌شود) — مگر در موارد
        نادر تداخل بین چند Site که با پسوند site_id یکتا می‌شود. تا وقتی
        has_custom_password=False است، password_hash یک مقدار تصادفی
        غیرقابل‌حدس است (نه چیزی که کسی واقعاً بداند) و ورود از مسیر کد
        پرسنلی/کد ملی انجام می‌شود.
        """
        result = await self.db.execute(select(User).where(User.employee_id == employee.id))
        user = result.scalar_one_or_none()
        if user is not None:
            if not user.is_active:
                user.is_active = True
                await self.db.commit()
            return user

        username = employee.personnel_code
        existing_username = await self.db.execute(select(User).where(User.username == username))
        if existing_username.scalar_one_or_none() is not None:
            # تداخل نادر (مثلاً همین کد پرسنلی در Site دیگری هم به یوزرنیم تبدیل شده)
            username = f"{employee.personnel_code}-{employee.site_id}"

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
        این مقدار کاملاً مستقل از is_active (که Sync Engine کنترل می‌کند) است
        و با هیچ Sync جدیدی بازنویسی نمی‌شود. اگر این پرسنل از قبل حساب کاربری
        داشته باشد (User)، همان لحظه User.is_active هم هماهنگ می‌شود تا
        غیرفعال‌سازی فوراً روی هر دو روش ورود (کد ملی و رمز اختصاصی) و حتی
        Session های باز فعلی اثر بگذارد — بدون این‌که رکورد User را اگر
        هنوز وجود ندارد، الکی بسازیم.
        """
        employee.is_enabled = enabled
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
        Admin مستقیماً یک رمز عبور مشخص برای پرسنل تعیین می‌کند. چون در login()
        ابتدا (یوزرنیم/پسورد) کاربر مدیریتی امتحان می‌شود و username این حساب
        همان personnel_code است، از این پس پرسنل با «کد پرسنلی + این رمز جدید»
        وارد می‌شود؛ has_custom_password=True می‌شود و از همین لحظه ورود با
        کد ملی دیگر برای این پرسنل کار نمی‌کند (طبق find_employee_for_login).

        must_change_password=True تنظیم می‌شود — چون این رمز را خودِ پرسنل
        انتخاب نکرده (Admin برایش تعیین کرده)، باید بعد از اولین ورود موفق
        مجبور شود یک رمز جدید (که فقط خودش می‌داند) تعیین کند.
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
        بازگرداندن پرسنل به روش ورود پیش‌فرض (کد پرسنلی + کد ملی)؛ رمز عبور
        اختصاصی قبلی از کار می‌افتد (با یک رمز تصادفی غیرقابل‌حدس جایگزین می‌شود).
        """
        user = await self.get_or_create_employee_user(employee)
        user.password_hash = hash_password(secrets.token_urlsafe(32))
        user.has_custom_password = False
        await self.db.commit()
        return user
