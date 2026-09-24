"""
نقطه ورود اصلی برنامه FAIPCO Portal: ساخت شیء FastAPI، چرخه عمر (همگام‌سازی
برندینگ index.html و استارت/توقف Scheduler)، CORS، ثبت روتر v1، Middleware
شمارش استفاده و endpoint سلامت.
اجرا: uvicorn app.main:app --reload
"""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.scheduler import start_scheduler, stop_scheduler
from app.api.v1.router import api_router
from app.services.usage_stats_service import record_usage

settings = get_settings()


async def sync_index_html_branding() -> None:
    """هنگام بالا آمدن سرویس، عنوان و نام کوتاه تنظیم‌شده در پنل را داخل dist/index.html می‌نویسد
    تا فایل تازه Build‌شده فرانت همیشه برندینگ فعلی را داشته باشد. خطا فقط لاگ می‌شود."""
    try:
        from app.db.session import AsyncSessionLocal
        from app.services.index_html_branding import write_index_html_branding
        from app.services.system_settings_service import SystemSettingsService

        # خواندن برندینگ از تنظیمات سیستم
        async with AsyncSessionLocal() as db:
            branding = await SystemSettingsService(db).get_branding()
        write_index_html_branding(branding["browser_title"], branding["manifest_short_name"])
    except Exception:  # noqa: BLE001 - نباید مانع بالا آمدن سرویس شود
        logging.getLogger(__name__).exception("همگام‌سازی عنوان index.html در شروع ناموفق بود")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """چرخه عمر برنامه: در شروع برندینگ را همگام و Scheduler را استارت می‌کند، در پایان Scheduler را متوقف می‌کند."""
    await sync_index_html_branding()
    await start_scheduler()
    yield
    stop_scheduler()


# شیء اصلی برنامه FastAPI
app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    lifespan=lifespan,
    # مستندات تعاملی API (Swagger/ReDoc/OpenAPI) فقط وقتی DEBUG=true است فعال‌اند
    # تا نقشه Endpointها روی Production بدون ورود در دسترس نباشد.
    docs_url="/api/docs" if settings.DEBUG else None,
    redoc_url="/api/redoc" if settings.DEBUG else None,
    openapi_url="/api/openapi.json" if settings.DEBUG else None,
)

# تنظیم CORS از روی CORS_ORIGINS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    # Credentials در CORS غیرفعال است: احراز هویت فقط با Bearer Token (نه Cookie) انجام می‌شود،
    # و ترکیب allow_origins=["*"] با allow_credentials=True باعث می‌شد Starlette هر Origin را منعکس کند.
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.API_V1_PREFIX)  # همه endpointهای v1 زیر /api/v1

# نگه‌داشتن ارجاع تسک‌های پس‌زمینه تا قبل از اتمام Garbage Collect نشوند
# (تسک در پایان کار با done_callback از Set حذف می‌شود).
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
    # فقط درخواست‌های API دارای هدر Authorization شمارش می‌شوند
    if request.url.path.startswith(settings.API_V1_PREFIX) and "authorization" in request.headers:
        task = asyncio.create_task(record_usage())
        _background_tasks.add(task)
        task.add_done_callback(_background_tasks.discard)

    return await call_next(request)


@app.get("/api/health", tags=["health"])
async def health_check():
    """endpoint سلامت برای Nginx/Monitoring؛ خروجی: وضعیت ok و نام برنامه."""
    return {"status": "ok", "app": settings.APP_NAME}
