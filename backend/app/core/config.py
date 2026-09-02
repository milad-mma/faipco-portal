"""
تنظیمات مرکزی برنامه.
تمام مقادیر حساس و قابل تغییر از طریق فایل .env خوانده می‌شوند
و هرگز نباید در کد Hardcode شوند.
"""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# مسیر backend/.env به‌صورت مطلق محاسبه می‌شود (نه نسبی) تا فرقی نکند
# برنامه از کجا اجرا می‌شود — چه از داخل backend/ (uvicorn) و چه از ریشه
# پروژه (مثلاً هنگام اجرای «python -m scripts.seed_permissions»).
# این فایل در backend/app/core/config.py است؛ سه سطح بالاتر یعنی backend/.
_BACKEND_DIR = Path(__file__).resolve().parent.parent.parent
_ENV_FILE_PATH = _BACKEND_DIR / ".env"


class Settings(BaseSettings):
    # --- برنامه ---
    APP_NAME: str = "FAIPCO Portal"
    # نسخه واقعی، از تگ Git — install.sh این را موقع هر نصب/آپدیت خودکار در
    # .env می‌نویسد؛ اگر اینجا اجرا نشده باشد (مثلاً محیط توسعه محلی)،
    # "dev" پیش‌فرض است.
    APP_VERSION: str = "dev"
    # مخزن GitHub — برای بررسی وجود نسخه جدید (پنل «بررسی آپدیت»). این
    # قابلیت کاملاً اختیاری و غیرمسدودکننده است — اگر اینترنت نبود یا
    # GitHub در دسترس نبود، فقط پیام «آپدیتی پیدا نشد» نشان داده می‌شود؛
    # هیچ بخش دیگری از برنامه تحت تأثیر قرار نمی‌گیرد.
    GITHUB_REPO: str = "milad-mma/faipco-portal"
    APP_ENV: str = "production"  # development | production
    DEBUG: bool = False
    API_V1_PREFIX: str = "/api/v1"

    # --- دیتابیس اصلی Portal ---
    DATABASE_URL: str  # مثال: postgresql+asyncpg://user:pass@localhost:5432/faipco

    # --- امنیت / JWT ---
    SECRET_KEY: str  # با: openssl rand -hex 32 تولید شود
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # --- رمزنگاری Credential های دیتابیس سایت‌ها ---
    # کلید مجزا از SECRET_KEY تا در صورت لو رفتن یکی، دیگری امن بماند
    DB_CREDENTIALS_ENCRYPTION_KEY: str  # با: Fernet.generate_key() تولید شود

    # --- CORS ---
    CORS_ORIGINS: list[str] = ["http://localhost:3000"]

    # --- آدرس Frontend (برای ساخت لینک‌های ایمیل، مثل بازنشانی رمز عبور) ---
    # ⚠️ هرگز از یک URL ای که خودِ کلاینت در درخواست فرستاده استفاده نشود
    # (ریسک فیشینگ) - همیشه از همین مقدار سرور-محور خوانده می‌شود.
    FRONTEND_URL: str = "http://localhost:3000"

    # --- Sync Engine ---
    SYNC_ENABLED: bool = True
    SYNC_INTERVAL_MINUTES: int = 30

    # --- Web Push (اعلان روی موبایل/دسکتاپ) ---
    # با: python -m scripts.generate_vapid_keys تولید می‌شوند
    VAPID_PUBLIC_KEY: str = ""
    VAPID_PRIVATE_KEY: str = ""
    VAPID_CLAIMS_EMAIL: str = "admin@example.com"

    # --- تولید PDF فیش حقوقی (Payroll Notice) ---
    # فونت اصلی Tahoma است (همان فونتی که خودِ گزارش SSRS سازمان با آن ساخته
    # شده — دقیق‌ترین تطابق ظاهری، مخصوصاً برای اعداد). اگر این فایل موجود
    # نباشد (مثلاً روی سرور دیگری بدون این فونت)، به‌صورت خودکار به DejaVu
    # Sans Condensed (که معمولاً از قبل روی سرور نصب است) سقوط می‌کند.
    # نکته حقوقی مهم: Tahoma یک فونت مالکیتی مایکروسافت است، نه متن‌باز —
    # توزیع مجدد آن ممکن است طبق شرایط لایسنس مایکروسافت مجاز نباشد. این
    # فایل صرفاً چون توسط کاربر این پروژه صراحتاً ارائه شده اینجا قرار گرفته؛
    # مسئولیت رعایت لایسنس بر عهده سازمان است.
    PERSIAN_FONT_PATH: str = str(_BACKEND_DIR / "app" / "assets" / "fonts" / "Tahoma.ttf")

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE_PATH,
        env_file_encoding="utf-8",
        case_sensitive=True,
    )


@lru_cache
def get_settings() -> Settings:
    """
    تنظیمات فقط یک‌بار خوانده و Cache می‌شود (به‌جای خواندن مکرر فایل .env).
    در همه‌ی جاهای برنامه با Depends(get_settings) استفاده شود.
    """
    return Settings()
