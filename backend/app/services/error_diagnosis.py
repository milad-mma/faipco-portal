"""
تشخیص «مشکل از کجاست و حالا چه کنم» برای هر گروه گزارش خطاها (docs/error-logs.md#تشخیص).

هر گروه یکی از این‌ها را می‌گیرد (level: ok = کاری لازم نیست، warn/critical = نیاز به اقدام، unknown = برای پشتیبانی):
- user_network   🟢 اینترنت همان کاربر (قطعی شبکه‌ی مرورگر، کمتر از NETWORK_CROWD کاربر در یک بازه)
- server_network 🔴 سرور یا شبکه (همان قطعی برای چند کاربر مختلف هم‌زمان)
- kara_data      🟠 داده‌ی نامعتبر یک پرسنل (مقدار بلندتر از ستون، قالب نادرست — معمولاً داده‌ی کاراوب)
- kara_config    🟠 اتصال یا تنظیمات کاراوب (ستون/جدول اشتباه در نگاشت، SQL Server در دسترس نیست)
- settings       🟠 تنظیمات ایمیل/پیامک/بکاپ/اعلان
- kara_slow      🟠 کندی کاراوب (درخواست کند در بخش‌های وابسته به کاراوب)
- server_slow    🔴 سرور پرتال کند (همان درخواست بارها کند)
- transient      🟢 کندی گذرا / نسخه‌ی قدیمی مرورگر
- portal_bug     🔴 باگ پرتال (خطای پیش‌بینی‌نشده‌ی سرور، صفحه‌ی سفید، خطای JavaScript)
- app_bug        🔴 باگ اپ اندروید
- unknown        ⚪ نامشخص

ورودی: ردیف گروه (dict با kind/category/source/message/last_request/last_user_label/hint) و آمار (distinct_ips_window =
تعداد IP متفاوت قطعی شبکه‌ی مرورگر در ±NETWORK_WINDOW آخرین رخداد، occurrences_24h). تابع خالص است (تست‌پذیر).
هر خطای تازه‌ای که «نامشخص» شد و علتش معلوم شد، یک قاعده این‌جا اضافه می‌شود.
"""
from __future__ import annotations

import re
from datetime import timedelta

NETWORK_CROWD = 3  # این تعداد کاربر (IP) متفاوت با قطعی شبکه در یک بازه = مشکل سرور/شبکه، نه اینترنت یک نفر
NETWORK_WINDOW = timedelta(minutes=15)
SLOW_REPEAT_24H = 5  # این تعداد درخواست کند یکسان در ۲۴ ساعت = سرور کند، نه گذرا
AUTO_RESOLVE_AFTER = timedelta(hours=24)  # گروه‌های «کاری لازم نیست» بعد از این مدت بی‌رخداد، خودکار «حل شد»

ACTION_LEVELS = ("warn", "critical", "unknown")

_DATA_PATTERNS = re.compile(
    r"value too long for type|StringDataRightTruncation|numeric field overflow|out of range for type|"
    r"invalid input syntax for type|String or binary data would be truncated|Conversion failed when converting",
    re.IGNORECASE,
)
_KARA_CONFIG_PATTERNS = re.compile(
    r"Invalid column name|Invalid object name|Login failed for user|Adaptive Server is unavailable|"
    r"DB-Lib error message 20009|Unable to connect|pymssql|mssql",
    re.IGNORECASE,
)
_CHUNK_PATTERNS = re.compile(
    r"ChunkLoadError|Loading chunk|Failed to fetch dynamically imported module|Importing a module script failed",
    re.IGNORECASE,
)
# مسیرهایی که پاسخشان به کاراوب (SQL Server) وابسته است؛ کندی آن‌ها معمولاً کندی کاراوب است
_KARA_ROUTES = re.compile(
    r"monthly-attendance|leave-request|/leave|/sync|attendance|turnover|missions?|forgotten|/kara|test-connection",
    re.IGNORECASE,
)
_SETTINGS_CATEGORIES = {"email": "ایمیل", "sms": "پیامک", "backup": "پشتیبان‌گیری", "push": "اعلان (Push)"}


def _out(key: str, level: str, title: str, action: str, subject: str | None = None) -> dict:
    return {"key": key, "level": level, "title": title, "action": action, "subject": subject}


def diagnose(item: dict, stats: dict | None = None) -> dict:
    """تشخیص یک گروه خطا. خروجی: {key, level, title, action, subject}."""
    stats = stats or {}
    kind = item.get("kind") or ""
    category = item.get("category") or ""
    message = item.get("message") or ""
    hint = item.get("hint")
    route = " ".join(str(item.get(k) or "") for k in ("source", "last_request"))
    user = item.get("last_user_label")

    # ۱. قطعی شبکه‌ی مرورگر: یک نفر یا چند نفر؟
    if kind == "client" and category == "network":
        ips = int(stats.get("distinct_ips_window") or 0)
        if ips >= NETWORK_CROWD:
            return _out(
                "server_network",
                "critical",
                "سرور یا شبکه (چند کاربر)",
                f"{ips} کاربر مختلف در یک بازه‌ی کوتاه به سرور نرسیدند. وضعیت سرور پرتال، Reverse Proxy و اینترنت "
                "شرکت را بررسی کنید.",
            )
        return _out(
            "user_network",
            "ok",
            "اینترنت همان کاربر",
            "کاری لازم نیست: قطعی لحظه‌ای اینترنت یک نفر (آنتن ضعیف، عوض شدن شبکه، VPN). بعد از ۲۴ ساعت خودکار "
            "«حل شد» می‌شود؛ اگر چند نفر هم‌زمان همین را بگیرند، این‌جا قرمز می‌شود.",
            user,
        )

    # ۲. داده‌ی نامعتبر (مقدار بلند/بدقالب) — تقریباً همیشه داده‌ی یک پرسنل از کاراوب
    if _DATA_PATTERNS.search(message):
        return _out(
            "kara_data",
            "warn",
            "داده‌ی نامعتبر یک پرسنل",
            ((hint + " ") if hint else "")
            + "اطلاعات یک پرسنل (معمولاً در کاراوب) طول یا قالب نادرست دارد؛ پرتال جلوی خطا را گرفته ولی بهتر است داده "
            "در کاراوب اصلاح شود. کد پیگیری را برای پشتیبانی بفرستید تا فیلد و پرسنل دقیق مشخص شود.",
            user,
        )

    # ۳. اتصال/تنظیمات کاراوب
    if category in ("kara", "sync") or _KARA_CONFIG_PATTERNS.search(message):
        if kind == "slow":
            pass  # درخواست کند در بخش کاراوب: پایین‌تر (kara_slow)
        else:
            return _out(
                "kara_config",
                "warn",
                "اتصال یا تنظیمات کاراوب",
                hint or "نگاشت‌های سایت (نام ستون‌ها و جدول‌ها) و اتصال SQL Server کاراوب را در «سایت‌ها» بررسی کنید.",
            )

    # ۴. تنظیمات ایمیل/پیامک/بکاپ/اعلان
    if category in _SETTINGS_CATEGORIES and kind == "error":
        label = _SETTINGS_CATEGORIES[category]
        return _out(
            "settings",
            "warn",
            f"تنظیمات {label}",
            hint or f"ارسال/اجرای {label} ناموفق بود؛ تنظیمات همین بخش را بررسی کنید (آدرس، رمز، دسترسی).",
        )

    # ۵. درخواست کند
    if kind == "slow":
        if _KARA_ROUTES.search(route):
            return _out(
                "kara_slow",
                "warn",
                "کندی کاراوب",
                "این بخش اطلاعاتش را از SQL Server کاراوب می‌خواند و پاسخ کاراوب دیر رسیده. یک‌بار مهم نیست؛ اگر "
                "مکرر شد، بار SQL Server یا شبکه‌ی بین پرتال و کاراوب را بررسی کنید.",
            )
        if int(stats.get("occurrences_24h") or 0) >= SLOW_REPEAT_24H:
            return _out(
                "server_slow",
                "critical",
                "سرور پرتال کند است",
                "این درخواست در ۲۴ ساعت اخیر بارها کند بوده. مصرف CPU و RAM سرور را در داشبورد ببینید و کد پیگیری را "
                "برای پشتیبانی بفرستید.",
            )
        return _out(
            "transient",
            "ok",
            "کندی گذرا",
            "یک‌بار (یا چندبار پراکنده) کند بوده؛ کاری لازم نیست مگر تکرار شود. بعد از ۲۴ ساعت خودکار «حل شد» می‌شود.",
        )

    # ۶. مرورگر کاربر
    if kind == "client":
        if _CHUNK_PATTERNS.search(message):
            return _out(
                "transient",
                "ok",
                "نسخه‌ی قدیمی در مرورگر کاربر",
                "کاری لازم نیست: بعد از آپدیت، تب باز قدیمی فایل‌های جدید را پیدا نکرده؛ با یک رفرش درست می‌شود.",
                user,
            )
        return _out(
            "portal_bug",
            "critical",
            "باگ پرتال" + (" (صفحه‌ی سفید)" if category == "frontend_crash" else ""),
            "این خطا از کد پرتال در مرورگر کاربر است. «جزئیات فنی» و کد پیگیری را برای پشتیبانی بفرستید.",
            user,
        )

    # ۷. اپ اندروید
    if kind == "android":
        return _out(
            "app_bug",
            "critical",
            "باگ اپ اندروید",
            "خطا در بخش بومی اپ اندروید. «جزئیات فنی» (شامل مدل گوشی و نسخه‌ی اپ) را برای پشتیبانی بفرستید.",
            user,
        )

    # ۸. خطای سرور
    if kind == "error":
        if (item.get("source") or "") == "faipco.http":
            return _out(
                "portal_bug",
                "critical",
                "باگ پرتال (خطای سرور)",
                "کاربر «خطای داخلی سرور» دیده است. کد پیگیری و «جزئیات فنی» را برای پشتیبانی بفرستید.",
                user,
            )
        if category == "database":
            return _out(
                "server_slow",
                "critical",
                "دیتابیس پرتال",
                hint or "دیتابیس پرتال (PostgreSQL) خطا داده یا اتصال‌هایش پر شده؛ سرویس postgresql و فضای دیسک را "
                "بررسی کنید و «جزئیات فنی» را برای پشتیبانی بفرستید.",
            )

    return _out(
        "unknown",
        "unknown",
        "نامشخص",
        ((hint + " ") if hint else "")
        + "این خطا هنوز شناخته‌شده نیست. «جزئیات فنی» را برای پشتیبانی بفرستید تا قاعده‌ی تشخیصش اضافه شود.",
        user,
    )


def needs_action(diagnosis: dict) -> bool:
    return diagnosis.get("level") in ACTION_LEVELS
