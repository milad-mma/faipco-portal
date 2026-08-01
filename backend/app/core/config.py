"""
تنظیمات مرکزی برنامه.
تمام مقادیر حساس و قابل تغییر از طریق فایل .env خوانده می‌شوند
و هرگز نباید در کد Hardcode شوند.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

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

    model_config = SettingsConfigDict(
        env_file=".env",
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
