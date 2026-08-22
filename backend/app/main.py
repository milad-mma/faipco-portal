"""
نقطه ورود اصلی برنامه FAIPCO Portal.
اجرا: uvicorn app.main:app --reload
"""
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.scheduler import start_scheduler, stop_scheduler
from app.api.v1.router import api_router
from app.services.usage_stats_service import record_usage

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

# نگه‌داشتن ارجاع تسک‌های پس‌زمینه — یک گوچای شناخته‌شده asyncio: اگر تسکی
# که با create_task ساخته شده هیچ‌جا نگه داشته نشود، ممکن است قبل از تمام
# شدن Garbage Collect شود. با افزودن به این Set (و حذف در پایان)، این خطر
# از بین می‌رود.
_background_tasks: set[asyncio.Task] = set()


@app.middleware("http")
async def track_usage_middleware(request: Request, call_next):
    """
    برای نمودار «میزان استفاده از پرتال» در پنل Admin — یک شمارنده ساعتی
    (نه لاگ تک‌تک درخواست‌ها). فقط برای درخواست‌های واقعاً احرازهویت‌شده
    (هدر Authorization دارند) به مسیرهای API شمارش می‌شود؛ نه health-check
    خودِ Nginx/Monitoring، نه فایل‌های استاتیک.

    با asyncio.create_task (نه await مستقیم) اجرا می‌شود — یعنی ثبت این آمار
    هیچ تأخیری به پاسخ واقعی کاربر اضافه نمی‌کند؛ حتی اگر خودِ ثبت کند یا
    شکست بخورد (که در خودِ record_usage با try/except پوشانده شده)، تأثیری
    روی درخواست اصلی ندارد.
    """
    if request.url.path.startswith(settings.API_V1_PREFIX) and "authorization" in request.headers:
        task = asyncio.create_task(record_usage())
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)

    return await call_next(request)


@app.get("/api/health", tags=["health"])
async def health_check():
    """برای بررسی سلامت سرویس توسط Nginx/Monitoring استفاده می‌شود."""
    return {"status": "ok", "app": settings.APP_NAME}
