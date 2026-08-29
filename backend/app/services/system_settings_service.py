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
LAST_BIRTHDAY_GREETINGS_DATE_KEY = "last_birthday_greetings_date"  # فرمت شمسی "YYYY-MM-DD"
LOGIN_BACKGROUND_DATA_KEY = "login_background_data"  # Base64
LOGIN_BACKGROUND_CONTENT_TYPE_KEY = "login_background_content_type"
APP_LOGO_DATA_KEY = "app_logo_data"  # Base64 — لوگوی درون‌برنامه‌ای عمومی (اسپلش، صفحه ورود، نوار بالا، پنل کاربری)
APP_LOGO_CONTENT_TYPE_KEY = "app_logo_content_type"
PWA_ICON_DATA_KEY = "pwa_icon_data"  # Base64 — آیکون اختصاصی Manifest/صفحه اصلی گوشی
PWA_ICON_CONTENT_TYPE_KEY = "pwa_icon_content_type"
FAVICON_DATA_KEY = "favicon_data"  # Base64 — آیکون اختصاصی تب مرورگر
FAVICON_CONTENT_TYPE_KEY = "favicon_content_type"

BROWSER_TITLE_KEY = "browser_title"  # عنوان تب مرورگر (document.title) — سراسر پروژه
MANIFEST_SHORT_NAME_KEY = "manifest_short_name"  # زیر آیکون، روی صفحه اصلی گوشی بعد از نصب PWA
MANIFEST_DESCRIPTION_KEY = "manifest_description"  # توضیح داخل خودِ Manifest (فروشگاه/دیالوگ نصب)
SPLASH_TITLE_KEY = "splash_title"
SPLASH_SUBTITLE_KEY = "splash_subtitle"
LOGIN_TITLE_KEY = "login_title"
LOGIN_SUBTITLE_KEY = "login_subtitle"
SIDEBAR_TITLE_KEY = "sidebar_title"  # نوار بالای پنل، کنار لوگو
PROFILE_TITLE_KEY = "profile_title"  # پنل کاربری، زیر لوگو
PROFILE_SUBTITLE_KEY = "profile_subtitle"

# مقادیر پیش‌فرض — همان چیزی که قبلاً همه‌جای پروژه Hard-code بود
DEFAULT_BROWSER_TITLE = "پرتال سازمانی پرسنل فایپکو"
DEFAULT_MANIFEST_SHORT_NAME = "فایپکو"
DEFAULT_MANIFEST_DESCRIPTION = "پرتال سازمانی مدیریت پرسنل و اطلاع‌رسانی"
DEFAULT_SPLASH_TITLE = "شرکت تولیدی صنعتی فواد الیاف"
DEFAULT_SPLASH_SUBTITLE = "سامانه مدیریت پرسنل"
DEFAULT_LOGIN_TITLE = "سامانه مدیریت پرسنل فایپکو"
DEFAULT_LOGIN_SUBTITLE = "شرکت تولیدی صنعتی فواد الیاف"
DEFAULT_SIDEBAR_TITLE = "فایپکو"
DEFAULT_PROFILE_TITLE = "شرکت تولیدی صنعتی فواد الیاف"
DEFAULT_PROFILE_SUBTITLE = "سامانه مدیریت پرسنل فایپکو"

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

    # ---------- کلید فعال/غیرفعال پیام تبریک تولد — مستقل از خالی/پر بودن پول ----------
    # ⚠️ رفع یک باگ حیاتی: این متد قبلاً دوبار در همین کلاس تعریف شده بود
    # — پایتون بی‌صدا فقط تعریف دومی را نگه می‌داشت (اولی کاملاً بی‌اثر و
    # مرده بود)، که رفتارش دقیقاً برعکس چیزی بود که کامنتش ادعا می‌کرد:
    # به‌جای «پیش‌فرض فعال، مگر صراحتاً خاموش شود» (raw != "false")، عملاً
    # «پیش‌فرض غیرفعال، مگر صراحتاً روشن شود» (raw == "true") اجرا می‌شد.
    # یعنی برای هر نصبی که Admin هرگز این کلید را صراحتاً «روشن» نکرده بود
    # (چون اصلاً انتظار نداشت نیاز به این کار باشد)، کل قابلیت تبریک تولد
    # همیشه، هر روز، بی‌صدا غیرفعال می‌ماند.

    async def get_birthday_greetings_enabled(self) -> bool:
        raw = await self._get_raw(BIRTHDAY_GREETINGS_ENABLED_KEY)
        # پیش‌فرض True است (برخلاف IP Allowlist) چون خودِ «پول خالی = ارسال نشدن»
        # از قبل یک محافظت کافی است؛ این کلید فقط برای خاموش‌کردن موقت است.
        return raw != "false"

    async def set_birthday_greetings_enabled(self, enabled: bool) -> bool:
        await self._set_raw(BIRTHDAY_GREETINGS_ENABLED_KEY, "true" if enabled else "false")
        return enabled

    async def get_last_birthday_greetings_date(self) -> str | None:
        """آخرین تاریخ شمسی (YYYY-MM-DD) که پیام تبریک تولد واقعاً ارسال شد — برای جلوگیری از ارسال تکراری."""
        return await self._get_raw(LAST_BIRTHDAY_GREETINGS_DATE_KEY)

    async def set_last_birthday_greetings_date(self, jalali_date: str) -> None:
        await self._set_raw(LAST_BIRTHDAY_GREETINGS_DATE_KEY, jalali_date)

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

    # ---------- برندینگ (لوگوها + متن‌های مجزای هر بخش) — «تنظیمات سامانه» ----------
    # ⚠️ همه این‌ها باید بدون احراز هویت هم در دسترس باشند — لوگو/متن‌ها
    # باید در اسپلش‌اسکرین/صفحه ورود (قبل از Login) و در خودِ Manifest PWA
    # (که مرورگر بدون هیچ Header ای می‌گیرد) هم درست نمایش داده شوند.

    # کلید‌های متنی + پیش‌فرض هرکدام — یک ساختار Generic برای جلوگیری از
    # تکرار ۷ متد تقریباً یکسان.
    _TEXT_FIELDS = {
        "browser_title": (BROWSER_TITLE_KEY, DEFAULT_BROWSER_TITLE),
        "manifest_short_name": (MANIFEST_SHORT_NAME_KEY, DEFAULT_MANIFEST_SHORT_NAME),
        "manifest_description": (MANIFEST_DESCRIPTION_KEY, DEFAULT_MANIFEST_DESCRIPTION),
        "splash_title": (SPLASH_TITLE_KEY, DEFAULT_SPLASH_TITLE),
        "splash_subtitle": (SPLASH_SUBTITLE_KEY, DEFAULT_SPLASH_SUBTITLE),
        "login_title": (LOGIN_TITLE_KEY, DEFAULT_LOGIN_TITLE),
        "login_subtitle": (LOGIN_SUBTITLE_KEY, DEFAULT_LOGIN_SUBTITLE),
        "sidebar_title": (SIDEBAR_TITLE_KEY, DEFAULT_SIDEBAR_TITLE),
        "profile_title": (PROFILE_TITLE_KEY, DEFAULT_PROFILE_TITLE),
        "profile_subtitle": (PROFILE_SUBTITLE_KEY, DEFAULT_PROFILE_SUBTITLE),
    }

    # کلید‌های سه لوگوی مجزا — هرکدام برای یک مصرف کاملاً متفاوت
    _LOGO_FIELDS = {
        "app_logo": (APP_LOGO_DATA_KEY, APP_LOGO_CONTENT_TYPE_KEY),
        "pwa_icon": (PWA_ICON_DATA_KEY, PWA_ICON_CONTENT_TYPE_KEY),
        "favicon": (FAVICON_DATA_KEY, FAVICON_CONTENT_TYPE_KEY),
    }

    async def get_branding(self) -> dict:
        texts = {}
        for field_name, (key, default) in self._TEXT_FIELDS.items():
            texts[field_name] = await self._get_raw(key) or default
        logos = {}
        for field_name, (data_key, _content_type_key) in self._LOGO_FIELDS.items():
            logos[f"has_custom_{field_name}"] = await self._get_raw(data_key) is not None
        return {**texts, **logos}

    async def set_branding(self, **fields: str | None) -> dict:
        """
        هر کلید باید یکی از _TEXT_FIELDS باشد؛ مقدار خالی/None یعنی «به
        پیش‌فرض برگرد» (ردیفش پاک می‌شود، نه این‌که رشته خالی ذخیره شود).
        """
        for field_name, value in fields.items():
            if field_name not in self._TEXT_FIELDS:
                continue
            key, _default = self._TEXT_FIELDS[field_name]
            if value:
                await self._set_raw(key, value)
            else:
                await self._delete_raw(key)
        return await self.get_branding()

    async def get_logo(self, which: str) -> tuple[bytes, str] | None:
        data_key, content_type_key = self._LOGO_FIELDS[which]
        raw = await self._get_raw(data_key)
        if raw is None:
            return None
        content_type = await self._get_raw(content_type_key) or "image/png"
        return base64.b64decode(raw), content_type

    async def set_logo(self, which: str, content: bytes, content_type: str) -> None:
        data_key, content_type_key = self._LOGO_FIELDS[which]
        await self._set_raw(data_key, base64.b64encode(content).decode("ascii"))
        await self._set_raw(content_type_key, content_type)

    async def delete_logo(self, which: str) -> None:
        data_key, content_type_key = self._LOGO_FIELDS[which]
        await self._delete_raw(data_key)
        await self._delete_raw(content_type_key)
