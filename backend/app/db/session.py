"""
مدیریت Session دیتابیس اصلی Portal (PostgreSQL): engine غیرهمزمان، کارخانه
AsyncSessionLocal، کلاس پایه Base برای مدل‌های ORM و Dependency get_db.
از الگوی Async Session استفاده می‌شود تا عملکرد بهتری زیر بار زیاد داشته باشیم.
"""
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from app.core.config import get_settings

settings = get_settings()

# engine اتصال asyncpg با Connection Pool
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,  # چاپ کوئری‌های SQL در حالت DEBUG
    pool_pre_ping=True,  # از قطع شدن Connection بی‌صدا جلوگیری می‌کند
    pool_size=10,  # تعداد Connectionهای ثابت Pool
    max_overflow=20,  # حداکثر Connection اضافه در بار زیاد
)

# کارخانه ساخت Session؛ در Endpointها (از طریق get_db) و Jobهای Scheduler استفاده می‌شود
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,  # اشیاء بعد از commit منقضی نشوند تا بدون کوئری مجدد قابل‌خواندن بمانند
)


class Base(DeclarativeBase):
    """کلاس پایه برای تمام مدل‌های ORM پروژه."""
    pass


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency استاندارد FastAPI برای تزریق Session دیتابیس در هر Endpoint؛ Session را yield و در پایان می‌بندد.
    استفاده: async def endpoint(db: AsyncSession = Depends(get_db)):
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
