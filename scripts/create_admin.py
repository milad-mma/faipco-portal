"""
ساخت اولین کاربر Admin سیستم (با نقش superadmin).
پیش‌نیاز: قبلاً scripts/seed_permissions.py اجرا شده باشد.

اجرا:
    python -m scripts.create_admin --username admin --password 'StrongPass123!' --email admin@example.com

این اسکریپت توسط install.sh در مرحله نصب هم به‌صورت خودکار فراخوانی می‌شود.
"""
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from sqlalchemy import select

from app.core.security import hash_password
from app.db.session import AsyncSessionLocal
from app.models.user import Role, User, UserRole


async def create_admin(username: str, password: str, email: str | None) -> None:
    async with AsyncSessionLocal() as db:
        result = await db.execute(select(User).where(User.username == username))
        if result.scalar_one_or_none() is not None:
            print(f"کاربر '{username}' از قبل وجود دارد؛ کاری انجام نشد.")
            return

        result = await db.execute(select(Role).where(Role.name == "superadmin"))
        superadmin_role = result.scalar_one_or_none()
        if superadmin_role is None:
            print("نقش superadmin پیدا نشد. ابتدا 'python -m scripts.seed_permissions' را اجرا کنید.")
            return

        user = User(
            username=username,
            email=email,
            password_hash=hash_password(password),
            is_active=True,
            is_superuser=True,
        )
        db.add(user)
        await db.flush()

        db.add(UserRole(user_id=user.id, role_id=superadmin_role.id, site_id=None))
        await db.commit()
        print(f"کاربر Admin '{username}' با موفقیت ساخته شد.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ساخت اولین کاربر Admin سیستم")
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--email", default=None)
    args = parser.parse_args()
    asyncio.run(create_admin(args.username, args.password, args.email))
