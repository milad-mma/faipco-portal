"""
لایه دسترسی به داده برای User.
محاسبه Permission های مؤثر کاربر (با در نظر گرفتن نقش‌های سراسری و Site-scoped) اینجا انجام می‌شود.
"""
from sqlalchemy import select, or_
from sqlalchemy.ext.asyncio import AsyncSession

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
