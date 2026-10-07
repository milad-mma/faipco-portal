"""
نقطه ورود اصلی برنامه FAIPCO Portal: ساخت شیء FastAPI، چرخه عمر (همگام‌سازی
برندینگ index.html و استارت/توقف Scheduler)، CORS، ثبت روتر v1، Middleware
شمارش استفاده و endpoint سلامت.
اجرا: uvicorn app.main:app --reload
"""
import logging
import secrets
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core import kara_pool
from app.core.ip_allowlist import get_client_ip
from app.core.request_context import (
    current_client_app,
    current_client_ip,
    current_request_id,
    current_request_label,
    current_user_agent,
)
from app.services import error_log_service

from app.core.config import get_settings
from app.core.scheduler import start_scheduler, stop_scheduler
from app.api.v1.router import api_router
from app.services.usage_stats_service import flush_usage, record_usage

settings = get_settings()

# گزارش خطاها: هر logger.error/exception در هر جای برنامه در دیتابیس هم ثبت می‌شود (docs/error-logs.md)
error_log_service.install_logging()


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
        # اثر انگشت کلید امضای اپ اندروید در assetlinks.json (بعد از هر Build فرانت دوباره نوشته می‌شود)
        from app.services.mobile_app_service import get_mobile_settings, write_assetlinks

        async with AsyncSessionLocal() as db:
            write_assetlinks((await get_mobile_settings(db)).signing_sha256)
    except Exception:  # noqa: BLE001 - نباید مانع بالا آمدن سرویس شود
        logging.getLogger(__name__).exception("همگام‌سازی عنوان index.html در شروع ناموفق بود")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    چرخه عمر برنامه: در شروع برندینگ را همگام و Scheduler را استارت می‌کند؛ در پایان Scheduler را
    متوقف و شمارنده‌ی در حافظه‌ی «میزان استفاده» را (تا شمارش دقیقه‌ی آخر گم نشود) به دیتابیس می‌نویسد.
    """
    error_log_service.start()
    await sync_index_html_branding()
    await start_scheduler()
    yield
    stop_scheduler()
    await error_log_service.stop()
    await flush_usage()
    kara_pool.close_all()  # اتصال‌های بی‌کار کاراوب


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

@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    """
    یک Middleware برای هر دو کار سبکِ هر درخواست:

    - User-Agent و هدر X-Client-App درخواست را برای لایه‌ی سرویس (ContextVar) در دسترس می‌گذارد.
    - برای نمودار «میزان استفاده از پرتال» در پنل Admin — یک شمارنده ساعتی (نه لاگ
      تک‌تک درخواست‌ها). فقط درخواست‌های واقعاً احرازهویت‌شده (هدر Authorization دارند)
      به مسیرهای API شمارش می‌شوند؛ نه health-check خودِ Nginx/Monitoring، نه فایل‌های
      استاتیک. شمارش فقط یک افزایش در حافظه‌ی Worker است (بدون Session/کوئری) و با Job
      دوره‌ای Scheduler و در shutdown به دیتابیس flush می‌شود، پس هیچ تأخیری به پاسخ
      کاربر اضافه نمی‌کند.
    """
    # فقط درخواست‌های API دارای هدر Authorization شمارش می‌شوند
    if request.url.path.startswith(settings.API_V1_PREFIX) and "authorization" in request.headers:
        record_usage()

    ua_token = current_user_agent.set(request.headers.get("user-agent", ""))
    app_token = current_client_app.set(request.headers.get("x-client-app", ""))
    # گزارش خطاها: کد پیگیری کوتاه برای هر درخواست (در هدر X-Request-ID و در پیام خطاهای ۵xx)
    request_id = secrets.token_hex(3).upper()
    path = request.url.path
    rid_token = current_request_id.set(request_id)
    label_token = current_request_label.set(f"{request.method} {path}")
    ip = get_client_ip(request)
    ip_token = current_client_ip.set(ip)
    started = time.perf_counter()
    status_code = 500
    try:
        try:
            response = await call_next(request)
        except Exception:  # noqa: BLE001 - خطای پیش‌بینی‌نشده‌ی Endpoint: ثبت با جزئیات کامل و پیام قابل‌پیگیری
            logging.getLogger("faipco.http").exception("خطای پیش‌بینی‌نشده در %s %s", request.method, path)
            response = JSONResponse(
                status_code=500,
                content={"detail": f"خطای داخلی سرور رخ داد. کد پیگیری: {request_id}"},
            )
        status_code = response.status_code
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        elapsed = time.perf_counter() - started
        if (
            elapsed >= error_log_service.SLOW_REQUEST_SECONDS
            and path.startswith(settings.API_V1_PREFIX)
            and not any(part in path for part in _SLOW_EXEMPT)
        ):
            route = getattr(request.scope.get("route"), "path", None) or path
            error_log_service.record_slow_request(
                request.method, route, path, elapsed, status_code, request_id,
                getattr(request.state, "user_ref", None), ip,
            )
        current_user_agent.reset(ua_token)
        current_client_app.reset(app_token)
        current_request_id.reset(rid_token)
        current_request_label.reset(label_token)
        current_client_ip.reset(ip_token)


# درخواست‌هایی که ذاتاً طولانی‌اند و «درخواست کند» حساب نمی‌شوند (بکاپ، بازیابی، آپدیت، فایل‌های حجیم)
_SLOW_EXEMPT = ("/backup", "/restore", "/apply-update", "/check-update", "/app/releases", "/download")


@app.exception_handler(StarletteHTTPException)
async def _http_exception_with_tracking_code(request: Request, exc: StarletteHTTPException):
    """خطاهای ۵xx (مثلاً «اتصال به کاراوب ناموفق بود») کد پیگیری درخواست را هم در پیام دارند."""
    if exc.status_code >= 500 and isinstance(exc.detail, str):
        request_id = current_request_id.get()
        if request_id and request_id not in exc.detail:
            exc = StarletteHTTPException(
                status_code=exc.status_code, detail=f"{exc.detail} (کد پیگیری: {request_id})", headers=exc.headers
            )
    return await http_exception_handler(request, exc)


@app.get("/api/health", tags=["health"])
async def health_check():
    """endpoint سلامت برای Nginx/Monitoring؛ خروجی: وضعیت ok و نام برنامه."""
    return {"status": "ok", "app": settings.APP_NAME}
