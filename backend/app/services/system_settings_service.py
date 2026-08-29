"""
سرویس تنظیمات سراسری قابل‌تغییر از پنل (بدون نیاز به ویرایش .env یا Restart سرور).
"""
import base64
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.system_setting import SystemSetting

SYNC_INTERVAL_KEY = "sync_interval_minutes"
LAST_AUTO_SYNC_AT_KEY = "last_auto_sync_at"  # ISO-format UTC — برای تشخیص «الان وقتشه یا نه» مستقل از هر Worker
IP_BLOCKED_MESSAGE_KEY = "ip_blocked_message"
IP_ALLOWLIST_ENABLED_KEY = "ip_allowlist_enabled"
BIRTHDAY_SEND_TIME_KEY = "birthday_send_time"  # فرمت "HH:MM"
BIRTHDAY_GREETINGS_ENABLED_KEY = "birthday_greetings_enabled"
LOGIN_BACKGROUND_DATA_KEY = "login_background_data"  # Base64
LOGIN_BACKGROUND_CONTENT_TYPE_KEY = "login_background_content_type"
APP_LOGO_DATA_KEY = "app_logo_data"  # Base64
APP_LOGO_CONTENT_TYPE_KEY = "app_logo_content_type"
APP_NAME_KEY = "app_name"
APP_SHORT_NAME_KEY = "app_short_name"
APP_DESCRIPTION_KEY = "app_description"

# مقادیر پیش‌فرض — همان چیزی که قبلاً همه‌جای پروژه Hard-code بود
DEFAULT_APP_NAME = "پرتال سازمانی پرسنل فایپکو"
DEFAULT_APP_SHORT_NAME = "فایپکو"
DEFAULT_APP_DESCRIPTION = "پرتال سازمانی مدیریت پرسنل و اطلاع‌رسانی"

DEFAULT_IP_BLOCKED_MESSAGE = (
    "دسترسی به پرتال فقط از شبکه مجاز (دفتر شرکت) امکان‌پذیر است. "
    "لطفاً اتصال VPN خود را قطع کنید و دوباره تلاش کنید."
)
DEFAULT_BIRTHDAY_SEND_TIME = "09:00"


class SystemSettingsService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def _get_raw(self, key: str) -> str | None:
        result = await self.db.execute(select(SystemSetting).where(SystemSetting.key == key))
        row = result.scalar_one_or_none()
        return row.value if row else None

    async def _set_raw(self, key: str, value: str) -> None:
        result = await self.db.execute(select(SystemSetting).where(SystemSetting.key == key))
        row = result.scalar_one_or_none()
        if row is None:
            self.db.add(SystemSetting(key=key, value=value))
        else:
            row.value = value
        await self.db.commit()

    async def _delete_raw(self, key: str) -> None:
        result = await self.db.execute(select(SystemSetting).where(SystemSetting.key == key))
        row = result.scalar_one_or_none()
        if row is not None:
            await self.db.delete(row)
            await self.db.commit()

    # ---------- فاصله زمانی Sync خودکار ----------

    async def get_sync_interval_minutes(self) -> int:
        """
        اگر هنوز از پنل تغییر داده نشده، مقدار پیش‌فرض همان SYNC_INTERVAL_MINUTES
        در .env است (سازگار با نصب‌های قبلی که این جدول را نداشتند).
        """
        raw = await self._get_raw(SYNC_INTERVAL_KEY)
        if raw is None:
            return get_settings().SYNC_INTERVAL_MINUTES
        return int(raw)

    async def set_sync_interval_minutes(self, minutes: int) -> int:
        if minutes < 1:
            raise ValueError("فاصله زمانی Sync باید حداقل ۱ دقیقه باشد")
        await self._set_raw(SYNC_INTERVAL_KEY, str(minutes))
        return minutes

    async def get_last_auto_sync_at(self) -> datetime | None:
        raw = await self._get_raw(LAST_AUTO_SYNC_AT_KEY)
        if raw is None:
            return None
        return datetime.fromisoformat(raw)

    async def set_last_auto_sync_at(self, when: datetime) -> None:
        await self._set_raw(LAST_AUTO_SYNC_AT_KEY, when.isoformat())

    # ---------- پیام نمایش‌داده‌شده وقتی IP کاربر مجاز نیست ----------

    async def get_ip_blocked_message(self) -> str:
        raw = await self._get_raw(IP_BLOCKED_MESSAGE_KEY)
        return raw if raw else DEFAULT_IP_BLOCKED_MESSAGE

    async def set_ip_blocked_message(self, message: str) -> str:
        message = message.strip()
        if not message:
            raise ValueError("متن پیام نمی‌تواند خالی باشد")
        await self._set_raw(IP_BLOCKED_MESSAGE_KEY, message)
        return message

    # ---------- کلید فعال/غیرفعال محدودیت IP — مستقل از این‌که رنجی ثبت شده یا نه ----------

    async def get_ip_allowlist_enabled(self) -> bool:
        raw = await self._get_raw(IP_ALLOWLIST_ENABLED_KEY)
        return raw == "true"

    async def set_ip_allowlist_enabled(self, enabled: bool) -> bool:
        await self._set_raw(IP_ALLOWLIST_ENABLED_KEY, "true" if enabled else "false")
        return enabled

    # ---------- ساعت ارسال روزانه پیام تبریک تولد ----------

    async def get_birthday_send_time(self) -> tuple[int, int]:
        """(ساعت, دقیقه) — پیش‌فرض ۰۹:۰۰."""
        raw = await self._get_raw(BIRTHDAY_SEND_TIME_KEY) or DEFAULT_BIRTHDAY_SEND_TIME
        hour_str, minute_str = raw.split(":")
        return int(hour_str), int(minute_str)

    async def set_birthday_send_time(self, hour: int, minute: int) -> tuple[int, int]:
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError("ساعت/دقیقه نامعتبر است")
        await self._set_raw(BIRTHDAY_SEND_TIME_KEY, f"{hour:02d}:{minute:02d}")
        return hour, minute

    # ---------- کلید فعال/غیرفعال پیام تبریک تولد — مستقل از خالی/پر بودن پول ----------

    async def get_birthday_greetings_enabled(self) -> bool:
        raw = await self._get_raw(BIRTHDAY_GREETINGS_ENABLED_KEY)
        # پیش‌فرض True است (برخلاف IP Allowlist) چون خودِ «پول خالی = ارسال نشدن»
        # از قبل یک محافظت کافی است؛ این کلید فقط برای خاموش‌کردن موقت است.
        return raw != "false"

    async def set_birthday_greetings_enabled(self, enabled: bool) -> bool:
        await self._set_raw(BIRTHDAY_GREETINGS_ENABLED_KEY, "true" if enabled else "false")
        return enabled

    # ---------- کلید فعال/غیرفعال پیام تبریک تولد — مستقل از خالی/پر بودن پول ----------

    async def get_birthday_greetings_enabled(self) -> bool:
        raw = await self._get_raw(BIRTHDAY_GREETINGS_ENABLED_KEY)
        return raw == "true"

    async def set_birthday_greetings_enabled(self, enabled: bool) -> bool:
        await self._set_raw(BIRTHDAY_GREETINGS_ENABLED_KEY, "true" if enabled else "false")
        return enabled

    # ---------- عکس پس‌زمینه صفحه ورود (قابلیت «تنظیمات سامانه») ----------
    # ⚠️ صفحه ورود قبل از احراز هویت نمایش داده می‌شود، پس Endpoint دریافت
    # این عکس باید کاملاً بدون نیاز به ورود در دسترس باشد — برخلاف عکس
    # پرسنلی (که همیشه پشت احراز هویت است). به همین دلیل این‌جا محتوا را
    # مستقیماً Base64 در همان جدول SystemSetting (نوع Text، بدون محدودیت
    # طول عملی در PostgreSQL) ذخیره می‌کنیم — بدون نیاز به یک Migration یا
    # مسیر ذخیره‌سازی فایل جداگانه.

    async def get_login_background(self) -> tuple[bytes, str] | None:
        """(محتوای باینری، content_type) یا None اگر هنوز چیزی آپلود نشده."""
        raw = await self._get_raw(LOGIN_BACKGROUND_DATA_KEY)
        if raw is None:
            return None
        content_type = await self._get_raw(LOGIN_BACKGROUND_CONTENT_TYPE_KEY) or "image/jpeg"
        return base64.b64decode(raw), content_type

    async def set_login_background(self, content: bytes, content_type: str) -> None:
        await self._set_raw(LOGIN_BACKGROUND_DATA_KEY, base64.b64encode(content).decode("ascii"))
        await self._set_raw(LOGIN_BACKGROUND_CONTENT_TYPE_KEY, content_type)

    async def delete_login_background(self) -> None:
        result = await self.db.execute(
            select(SystemSetting).where(
                SystemSetting.key.in_([LOGIN_BACKGROUND_DATA_KEY, LOGIN_BACKGROUND_CONTENT_TYPE_KEY])
            )
        )
        for row in result.scalars().all():
            await self.db.delete(row)
        await self.db.commit()

    # ---------- برندینگ (لوگو + نام اپ) — قابلیت «تنظیمات سامانه» ----------
    # ⚠️ همه این‌ها باید بدون احراز هویت هم در دسترس باشند — لوگو و اسم اپ
    # باید در اسپلش‌اسکرین/صفحه ورود (قبل از Login) و در خودِ Manifest PWA
    # (که مرورگر بدون هیچ Header ای می‌گیرد) هم درست نمایش داده شوند.

    async def get_branding(self) -> dict:
        name = await self._get_raw(APP_NAME_KEY)
        short_name = await self._get_raw(APP_SHORT_NAME_KEY)
        description = await self._get_raw(APP_DESCRIPTION_KEY)
        has_custom_logo = await self._get_raw(APP_LOGO_DATA_KEY) is not None
        return {
            "name": name or DEFAULT_APP_NAME,
            "short_name": short_name or DEFAULT_APP_SHORT_NAME,
            "description": description or DEFAULT_APP_DESCRIPTION,
            "has_custom_logo": has_custom_logo,
        }

    async def set_branding(
        self, *, name: str | None, short_name: str | None, description: str | None
    ) -> dict:
        # رشته خالی یعنی «به پیش‌فرض برگرد» — پس هرکدام که خالی/None بود، ردیفش پاک می‌شود
        if name:
            await self._set_raw(APP_NAME_KEY, name)
        else:
            await self._delete_raw(APP_NAME_KEY)
        if short_name:
            await self._set_raw(APP_SHORT_NAME_KEY, short_name)
        else:
            await self._delete_raw(APP_SHORT_NAME_KEY)
        if description:
            await self._set_raw(APP_DESCRIPTION_KEY, description)
        else:
            await self._delete_raw(APP_DESCRIPTION_KEY)
        return await self.get_branding()

    async def get_app_logo(self) -> tuple[bytes, str] | None:
        raw = await self._get_raw(APP_LOGO_DATA_KEY)
        if raw is None:
            return None
        content_type = await self._get_raw(APP_LOGO_CONTENT_TYPE_KEY) or "image/png"
        return base64.b64decode(raw), content_type

    async def set_app_logo(self, content: bytes, content_type: str) -> None:
        await self._set_raw(APP_LOGO_DATA_KEY, base64.b64encode(content).decode("ascii"))
        await self._set_raw(APP_LOGO_CONTENT_TYPE_KEY, content_type)

    async def delete_app_logo(self) -> None:
        await self._delete_raw(APP_LOGO_DATA_KEY)
        await self._delete_raw(APP_LOGO_CONTENT_TYPE_KEY)
