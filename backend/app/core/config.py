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

    # --- Sync Engine ---
    SYNC_ENABLED: bool = True
    SYNC_INTERVAL_MINUTES: int = 30

    # --- Web Push (اعلان روی موبایل/دسکتاپ) ---
    # با: python -m scripts.generate_vapid_keys تولید می‌شوند
    VAPID_PUBLIC_KEY: str = ""
    VAPID_PRIVATE_KEY: str = ""
    VAPID_CLAIMS_EMAIL: str = "admin@example.com"

    # --- تولید PDF فیش حقوقی (Payroll Notice) ---
    # یک فونت TTF فارسی/عربی (مثلاً Vazirmatn) باید در این مسیر قرار بگیرد تا
    # متن فارسی در PDF درست (با اتصال حروف و راست‌به‌چپ) نمایش داده شود. اگر
    # فایل موجود نباشد، به فونت پیش‌فرض بدون پشتیبانی فارسی سقوط می‌کند (فقط
    # اعداد/حروف لاتین درست دیده می‌شوند) و یک هشدار در Log ثبت می‌شود.
    PERSIAN_FONT_PATH: str = str(_BACKEND_DIR / "app" / "assets" / "fonts" / "Vazirmatn-Regular.ttf")

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
