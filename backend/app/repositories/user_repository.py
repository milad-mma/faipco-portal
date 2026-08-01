"""
لایه دسترسی به داده برای User.
محاسبه Permission های مؤثر کاربر (با در نظر گرفتن نقش‌های سراسری و Site-scoped) اینجا انجام می‌شود.
همچنین منطق «پیدا کردن پرسنل برای ورود» و «ساخت خودکار حساب کاربری متصل به پرسنل» اینجاست.
"""
import secrets

from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
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

    # ---------- ورود پرسنل (کد پرسنلی + کد ملی) ----------

    async def find_employee_for_login(self, personnel_code: str, national_code: str) -> Employee | None:
        """
        پرسنل فعالی که هم کد پرسنلی و هم کد ملی‌اش دقیقاً مطابقت داشته باشد را برمی‌گرداند.
        اگر (به‌ندرت) بین سایت‌های مختلف کد پرسنلی تکراری باشد، اولین مورد فعال برگردانده می‌شود.
        """
        result = await self.db.execute(
            select(Employee).where(
                Employee.personnel_code == personnel_code.strip(),
                Employee.national_code == national_code.strip(),
                Employee.is_active.is_(True),
            )
        )
        return result.scalars().first()

    async def get_or_create_employee_user(self, employee: Employee) -> User:
        """
        هر پرسنل یک حساب User مرتبط (از طریق employee_id) دارد که اولین بار
        هنگام ورود موفق، به‌صورت خودکار ساخته می‌شود. رمز عبور این حساب هرگز
        استفاده نمی‌شود (ورود همیشه از مسیر کد پرسنلی/کد ملی انجام می‌شود)،
        فقط برای رعایت الزام NOT NULL ستون password_hash یک مقدار تصادفی و
        غیرقابل‌حدس ذخیره می‌شود.
        """
        result = await self.db.execute(select(User).where(User.employee_id == employee.id))
        user = result.scalar_one_or_none()
        if user is not None:
            if not user.is_active:
                user.is_active = True
                await self.db.commit()
            return user

        username = f"emp{employee.id}"
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
