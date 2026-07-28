"""
Seed اولیه Permission ها و نقش‌های سیستمی پایه.
این اسکریپت Idempotent است (اجرای چندباره مشکلی ایجاد نمی‌کند).

اجرا:
    cd backend
    python -m scripts.seed_permissions
"""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from sqlalchemy import select

from app.db.session import AsyncSessionLocal
from app.models.user import Permission, Role, RolePermission

# فهرست کامل Permission های پایه سیستم — با اضافه شدن ماژول جدید، اینجا هم باید اضافه شود
DEFAULT_PERMISSIONS = [
    ("employees.view", "مشاهده لیست پرسنل"),
    ("employees.create", "افزودن دستی پرسنل"),
    ("employees.update", "ویرایش اطلاعات پرسنل"),
    ("sites.view", "مشاهده سایت‌ها"),
    ("sites.manage", "مدیریت سایت‌ها و اتصال دیتابیس"),
    ("sync.view", "مشاهده وضعیت Sync"),
    ("sync.run", "اجرای دستی Sync"),
    ("notices.view", "مشاهده اطلاعیه‌ها"),
    ("notices.create", "ایجاد اطلاعیه"),
    ("roles.manage", "مدیریت نقش‌ها و مجوزها"),
    ("users.manage", "مدیریت کاربران Portal"),
]


async def seed() -> None:
    async with AsyncSessionLocal() as db:
        # 1. Permission ها
        code_to_permission: dict[str, Permission] = {}
        for code, description in DEFAULT_PERMISSIONS:
            result = await db.execute(select(Permission).where(Permission.code == code))
            perm = result.scalar_one_or_none()
            if perm is None:
                perm = Permission(code=code, description=description)
                db.add(perm)
                await db.flush()
            code_to_permission[code] = perm

        # 2. نقش سیستمی superadmin با همه Permission ها
        result = await db.execute(select(Role).where(Role.name == "superadmin"))
        superadmin_role = result.scalar_one_or_none()
        if superadmin_role is None:
            superadmin_role = Role(
                name="superadmin", description="دسترسی کامل به تمام بخش‌های سیستم", is_system=True
            )
            db.add(superadmin_role)
            await db.flush()

        for perm in code_to_permission.values():
            result = await db.execute(
                select(RolePermission).where(
                    RolePermission.role_id == superadmin_role.id,
                    RolePermission.permission_id == perm.id,
                )
            )
            if result.scalar_one_or_none() is None:
                db.add(RolePermission(role_id=superadmin_role.id, permission_id=perm.id))

        await db.commit()
        print(f"Seed کامل شد: {len(code_to_permission)} Permission، نقش superadmin آماده است.")


if __name__ == "__main__":
    asyncio.run(seed())
