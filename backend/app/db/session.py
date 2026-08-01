"""
مدیریت Session دیتابیس اصلی Portal (PostgreSQL).
از الگوی Async Session استفاده می‌شود تا عملکرد بهتری زیر بار زیاد داشته باشیم.
"""
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

settings = get_settings()

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_pre_ping=True,  # از قطع شدن Connection بی‌صدا جلوگیری می‌کند
    pool_size=10,
    max_overflow=20,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    """کلاس پایه برای تمام مدل‌های ORM پروژه."""
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency استاندارد FastAPI برای تزریق Session دیتابیس در هر Endpoint.
    استفاده: async def endpoint(db: AsyncSession = Depends(get_db)):
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
