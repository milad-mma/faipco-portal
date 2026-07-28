#!/usr/bin/env python3
"""
Seed اولیه Permission های سیستمی.
این اسکریپت بعد از 'alembic upgrade head' اجرا می‌شود.
اجرا: python -m scripts.seed_permissions
"""
import asyncio
import sys
import os

# مسیر backend را به sys.path اضافه می‌کند
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), '..', 'backend', '.env'))

DATABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+asyncpg://faipco_user:password@localhost:5432/faipco_portal"
)

PERMISSIONS = [
    ("employees.view",       "مشاهده لیست پرسنل"),
    ("employees.update",     "ویرایش اطلاعات پرسنل"),
    ("sites.view",           "مشاهده سایت‌ها"),
    ("sites.create",         "ایجاد و ویرایش سایت"),
    ("sites.sync",           "همگام‌سازی پرسنل سایت"),
    ("notices.view",         "مشاهده اطلاعیه‌ها"),
    ("notices.create",       "ایجاد و انتشار اطلاعیه"),
    ("departments.view",     "مشاهده واحدهای سازمانی"),
    ("departments.create",   "ایجاد و ویرایش واحد"),
    ("reports.view",         "مشاهده گزارشات"),
]


async def seed():
    engine = create_async_engine(DATABASE_URL, echo=False)
    SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with SessionLocal() as db:
        # import اینجا تا مسیر sys.path درست باشد
        from app.models import Permission

        created = 0
        for name, description in PERMISSIONS:
            result = await db.execute(
                select(Permission).where(Permission.name == name)
            )
            if not result.scalar_one_or_none():
                db.add(Permission(name=name, description=description))
                print(f"  ✔ Created permission: {name}")
                created += 1
            else:
                print(f"  - Already exists: {name}")

        await db.commit()
        print(f"\nSeed complete: {created} new permissions created.")

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(seed())
