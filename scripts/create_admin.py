#!/usr/bin/env python3
"""
ساخت کاربر Admin اولیه.
اجرا: python -m scripts.create_admin --username admin --password 'StrongPass123!'
"""
import asyncio
import argparse
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), '..', 'backend', '.env'))

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://faipco_user:password@localhost:5432/faipco_portal"
)


async def create_admin(username: str, password: str, email: str):
    from sqlalchemy import select
    from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
    from app.models import User
    from app.core.security import get_password_hash

    engine = create_async_engine(DATABASE_URL, echo=False)
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with SessionLocal() as db:
        result = await db.execute(select(User).where(User.username == username))
        existing = result.scalar_one_or_none()

        if existing:
            # اگر وجود داشت، فقط رمز و superuser را آپدیت می‌کند
            existing.hashed_password = get_password_hash(password)
            existing.is_superuser = True
            existing.is_active = True
            await db.commit()
            print(f"  ✔ Updated existing user: {username}")
        else:
            user = User(
                username=username,
                email=email,
                hashed_password=get_password_hash(password),
                is_superuser=True,
                is_active=True,
                full_name="مدیر سیستم",
            )
            db.add(user)
            await db.commit()
            print(f"  ✔ Created admin user: {username}")

    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="ساخت کاربر Admin")
    parser.add_argument("--username", required=True, help="نام کاربری")
    parser.add_argument("--password", required=True, help="رمز عبور")
    parser.add_argument("--email", default="admin@faipco.local", help="ایمیل")
    args = parser.parse_args()

    asyncio.run(create_admin(args.username, args.password, args.email))
