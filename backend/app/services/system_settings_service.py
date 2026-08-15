"""
سرویس تنظیمات سراسری قابل‌تغییر از پنل (بدون نیاز به ویرایش .env یا Restart سرور).
"""
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.models.system_setting import SystemSetting

SYNC_INTERVAL_KEY = "sync_interval_minutes"
IP_BLOCKED_MESSAGE_KEY = "ip_blocked_message"
IP_ALLOWLIST_ENABLED_KEY = "ip_allowlist_enabled"
BIRTHDAY_SEND_TIME_KEY = "birthday_send_time"  # فرمت "HH:MM"
BIRTHDAY_GREETINGS_ENABLED_KEY = "birthday_greetings_enabled"
BIRTHDAY_GREETINGS_ENABLED_KEY = "birthday_greetings_enabled"

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
