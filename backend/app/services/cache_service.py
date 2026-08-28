"""
سرویس «پاک‌کردن کش اپلیکیشن برای همه کاربران».

نکته پلتفرمی مهم: هیچ API وبی وجود ندارد که سرور بتواند از راه دور کش
مرورگر یک کاربر را پاک کند. تنها راه واقعی و قانونی این است که خودِ فایل
sw.js از نظر بایتی تغییر کند — مرورگر هر کاربر، هر بار که به سایت سر می‌زند،
محتوای sw.js را دوباره می‌گیرد و اگر با نسخه نصب‌شده فرق داشته باشد، نسخه
جدید را نصب می‌کند؛ Workbox (که این پروژه با آن ساخته شده)، در فاز
activate خودش، هر Cache قدیمی مرتبط با نسخه Precache قبلی را پاک می‌کند.

⚠️ رفع یک باگ واقعی: این تابع قبلاً دنبال یک الگوی متنی خاص
(`const CACHE_NAME = "faipco-shell-v...";`) داخل sw.js می‌گشت — که مربوط
به یک نسخه خیلی قدیمی‌تر sw.js بود (قبل از این‌که این پروژه به Workbox
مهاجرت کند، که خودش نسخه‌بندی Cache را از طریق `self.__WB_MANIFEST`
مدیریت می‌کند، نه یک ثابت دستی). چون این الگو در sw.js فعلی اصلاً وجود
ندارد، هر بار این دکمه زده می‌شد، بلافاصله با خطای «الگو پیدا نشد» شکست
می‌خورد — یعنی این قابلیت از مدت‌ها پیش کاملاً از کار افتاده بود.

رفع، با یک روش ساده‌تر و مستقل از جزئیات داخلی Workbox: به‌جای دنبال‌کردن
یک ثابت خاص، همین‌جا یک خط Comment با یک برچسب‌زمانی تازه به انتهای sw.js
اضافه/به‌روزرسانی می‌شود. همین تغییرِ حتی یک بایت، برای مرورگر کافی است تا
sw.js را «تغییر‌کرده» تشخیص دهد و چرخه عادی نصب/فعال‌سازی نسخه جدید (که
Workbox داخلش Cache قدیمی را پاک می‌کند) را شروع کند.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path


class CacheBustError(Exception):
    pass


# frontend/dist در کنار backend/ قرار دارد (هر دو زیر ریشه پروژه)
_FRONTEND_SW_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent / "frontend" / "dist" / "sw.js"
)

_BUST_MARKER_PATTERN = re.compile(r"\n// cache-bust: [^\n]*\n?$")


def bump_app_cache_version() -> str:
    if not _FRONTEND_SW_PATH.exists():
        raise CacheBustError(f"فایل sw.js پیدا نشد: {_FRONTEND_SW_PATH}")

    content = _FRONTEND_SW_PATH.read_text(encoding="utf-8")
    new_version = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    marker = f"\n// cache-bust: {new_version}\n"

    # اگر از قبل یک برچسب cache-bust در انتهای فایل بود، جایگزینش می‌کنیم؛
    # وگرنه یکی جدید اضافه می‌کنیم — تا فایل با هر بار کلیک بی‌نهایت بزرگ نشود.
    if _BUST_MARKER_PATTERN.search(content):
        new_content = _BUST_MARKER_PATTERN.sub(marker, content)
    else:
        new_content = content.rstrip("\n") + "\n" + marker.lstrip("\n")

    # نوشتن Atomic — یا فایل کاملاً جایگزین می‌شود یا اصلاً دست‌نخورده می‌ماند
    tmp_path = _FRONTEND_SW_PATH.with_suffix(".js.tmp")
    tmp_path.write_text(new_content, encoding="utf-8")
    tmp_path.replace(_FRONTEND_SW_PATH)

    return new_version
