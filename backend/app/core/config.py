"""
تنظیمات مرکزی برنامه (کلاس Settings مبتنی بر pydantic-settings) و تابع get_settings.
تمام مقادیر حساس و قابل تغییر از طریق فایل backend/.env خوانده می‌شوند
و هرگز نباید در کد Hardcode شوند.
"""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# مسیر backend/.env به‌صورت مطلق محاسبه می‌شود تا مستقل از پوشه اجرای برنامه باشد
# (چه uvicorn از داخل backend/، چه اسکریپت‌ها از ریشه پروژه).
# این فایل در backend/app/core/config.py است؛ سه سطح بالاتر یعنی backend/.
_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
_ENV_FILE_PATH = _BACKEND_DIR / ".env"


class Settings(BaseSettings):
    """
    همه تنظیمات برنامه؛ هر فیلد از متغیر هم‌نام در .env (یا محیط) خوانده می‌شود.
    فیلدهای بدون مقدار پیش‌فرض اجباری‌اند و نبودشان هنگام Startup خطا می‌دهد.
    """

    # --- برنامه ---
    APP_NAME: str = "FAIPCO Portal"  # نام برنامه در عنوان API و خروجی‌ها
    # نسخه برنامه از تگ Git؛ install.sh هنگام نصب/آپدیت در .env می‌نویسد، در محیط توسعه "dev"
    APP_VERSION: str = "dev"
    # کانال آپدیت (install.sh می‌نویسد): "tag" = فقط آخرین تگ/ریلیز، "branch" = آخرین commit شاخه
    UPDATE_CHANNEL: str = "tag"
    # مخزن GitHub برای بررسی وجود نسخه جدید در پنل «بررسی آپدیت»؛ در نبود اینترنت
    # فقط پیام «آپدیتی پیدا نشد» نمایش داده می‌شود و بقیه برنامه تأثیری نمی‌پذیرد.
    GITHUB_REPO: str = "milad-mma/faipco-portal"
    APP_ENV: str = "production"  # development | production
    DEBUG: bool = False  # فعال‌سازی حالت دیباگ FastAPI
    API_V1_PREFIX: str = "/api/v1"  # پیشوند مسیر همه endpointهای نسخه v1

    # --- دیتابیس اصلی Portal ---
    DATABASE_URL: str  # مثال: postgresql+asyncpg://user:pass@localhost:5432/faipco

    # --- امنیت / JWT ---
    SECRET_KEY: str  # با: openssl rand -hex 32 تولید شود
    ALGORITHM: str = "HS256"  # الگوریتم امضای JWT
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60  # عمر Access Token به دقیقه
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30  # عمر Refresh Token به روز

    # --- رمزنگاری Credential های دیتابیس سایت‌ها ---
    # کلید مجزا از SECRET_KEY تا در صورت لو رفتن یکی، دیگری امن بماند
    DB_CREDENTIALS_ENCRYPTION_KEY: str  # با: Fernet.generate_key() تولید شود

    # --- CORS ---
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]  # Originهای مجاز برای درخواست‌های مرورگر

    # --- آدرس Frontend (برای ساخت لینک‌های ایمیل، مثل بازنشانی رمز عبور) ---
    # لینک‌ها همیشه از همین مقدار سمت سرور ساخته می‌شوند، نه از URL ارسالی کلاینت (جلوگیری از فیشینگ)
    FRONTEND_URL: str = "http://localhost:3000"

    # --- Sync Engine ---
    SYNC_ENABLED: bool = True  # روشن/خاموش بودن همگام‌سازی دوره‌ای با دیتابیس سایت‌ها
    SYNC_INTERVAL_MINUTES: int = 30  # فاصله پیش‌فرض بین دو همگام‌سازی به دقیقه

    # --- Web Push (اعلان روی موبایل/دسکتاپ) ---
    # با: python -m scripts.generate_vapid_keys تولید می‌شوند
    VAPID_PUBLIC_KEY: str = ""  # کلید عمومی VAPID که به مرورگر داده می‌شود
    VAPID_PRIVATE_KEY: str = ""  # کلید خصوصی امضای پیام‌های Push
    VAPID_CLAIMS_EMAIL: str = "admin@example.com"  # ایمیل تماس در claim های VAPID

    # --- تولید PDF فیش حقوقی (Payroll Notice) ---
    # مسیر فونت فارسی PDF؛ Tahoma برای تطابق ظاهری با گزارش SSRS سازمان استفاده می‌شود
    # و اگر فایل موجود نباشد، به‌صورت خودکار DejaVu Sans Condensed جایگزین می‌شود.
    # Tahoma فونت مالکیتی مایکروسافت است؛ مسئولیت رعایت لایسنس آن بر عهده سازمان است.
    PERSIAN_FONT_PATH: str = str(_BACKEND_DIR / "app" / "assets" / "fonts" / "Tahoma.ttf")

    # پیکربندی خواندن .env: مسیر مطلق فایل، کدگذاری UTF-8 و حساسیت به حروف بزرگ/کوچک نام متغیرها
    model_config = SettingsConfigDict(
        env_file=_ENV_FILE_PATH,
        env_file_encoding="utf-8",
        case_sensitive=True,
    )


@lru_cache
def get_settings() -> Settings:
    """
    شیء Settings را برمی‌گرداند؛ فقط یک‌بار خوانده و Cache می‌شود (به‌جای خواندن مکرر .env).
    در همه‌ی جاهای برنامه با Depends(get_settings) یا فراخوانی مستقیم استفاده می‌شود.
    """
    return Settings()
