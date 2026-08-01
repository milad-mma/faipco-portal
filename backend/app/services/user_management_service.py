"""منطق تجاری مدیریت کاربران و انتصاب نقش (Role) — پایه سلسله‌مراتب ارسال اطلاعیه."""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import Role, User, UserRole
from app.schemas.user_management import AssignRoleIn


class UserManagementService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_users(self) -> list[User]:
        result = await self.db.execute(select(User))
        return list(result.scalars().all())

    async def list_roles(self) -> list[Role]:
        result = await self.db.execute(select(Role))
        return list(result.scalars().all())

    async def list_user_roles(self, user_id: int) -> list[UserRole]:
        result = await self.db.execute(select(UserRole).where(UserRole.user_id == user_id))
        return list(result.scalars().all())

    async def assign_role(self, user_id: int, payload: AssignRoleIn) -> UserRole:
        user_role = UserRole(user_id=user_id, role_id=payload.role_id, site_id=payload.site_id)
        self.db.add(user_role)
        await self.db.commit()
        await self.db.refresh(user_role)
        return user_role

    async def remove_role_assignment(self, user_role_id: int) -> bool:
        user_role = await self.db.get(UserRole, user_role_id)
        if user_role is None:
            return False
        await self.db.delete(user_role)
        await self.db.commit()
        return True
