"""
نقطه ورود اصلی برنامه FAIPCO Portal.
اجرا: uvicorn app.main:app --reload
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.scheduler import start_scheduler, stop_scheduler
from app.api.v1.router import api_router

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    await start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    lifespan=lifespan,
    # مستندات تعاملی API (Swagger/ReDoc) فقط وقتی DEBUG=true فعال است —
    # روی Production این‌ها نقشه کامل هر Endpoint را بدون نیاز به ورود در
    # اختیار هرکسی می‌گذارند؛ چیزی که یک مهاجم را از حدس‌زدن/Fuzz کردن
    # مسیرها بی‌نیاز می‌کند. توسعه‌دهنده‌ها می‌توانند موقتاً DEBUG=true را
    # روی سرور خودشان (نه Production واقعی) فعال کنند.
    docs_url="/api/docs" if settings.DEBUG else None,
    redoc_url="/api/redoc" if settings.DEBUG else None,
    openapi_url="/api/openapi.json" if settings.DEBUG else None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    # قبلاً True بود — همراه با allow_origins=["*"] (که در Production واقعی
    # تنظیم می‌شود)، این ترکیب باعث می‌شد Starlette به‌جای فرستادن "*" خام،
    # مقدار Origin هر درخواست را عیناً در پاسخ منعکس کند (رفتار شناخته‌شده
    # Starlette برای دورزدن محدودیت مرورگرها روی wildcard+credentials) —
    # یعنی عملاً هر سایتی می‌توانست درخواست Cross-Origin با Credentials
    # بفرستد. چون این پروژه هیچ‌جا از Cookie برای احراز هویت استفاده نمی‌کند
    # (فقط Bearer Token از localStorage، که به‌طور خودکار توسط مرورگر برای
    # درخواست‌های Cross-Origin فرستاده نمی‌شود)، اصلاً نیازی به Credentials
    # در CORS نیست — False کردنش این حفره را کاملاً می‌بندد، بدون تأثیر بر
    # عملکرد فعلی (چون فرانت‌اند همیشه Same-Origin وصل می‌شود).
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_PREFIX)


@app.get("/api/health", tags=["health"])
async def health_check():
    """برای بررسی سلامت سرویس توسط Nginx/Monitoring استفاده می‌شود."""
    return {"status": "ok", "app": settings.APP_NAME}
