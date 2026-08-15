"""
سرویس «پاک‌کردن کش اپلیکیشن برای همه کاربران».

نکته پلتفرمی مهم: هیچ API وبی وجود ندارد که سرور بتواند از راه دور کش
مرورگر یک کاربر را پاک کند. تنها راه واقعی و قانونی این است که خودِ فایل
sw.js از نظر بایتی تغییر کند — مرورگر هر کاربر، هر بار که به سایت سر می‌زند،
محتوای sw.js را دوباره می‌گیرد و اگر با نسخه نصب‌شده فرق داشته باشد، نسخه
جدید را نصب می‌کند. منطق activate() داخل خودِ sw.js از قبل هر Cache قدیمی
(با نام متفاوت از CACHE_NAME جدید) را پاک می‌کند — یعنی نتیجه دقیقاً همان
چیزی است که خواسته شده: انگار کاربر اولین‌بار دارد اپ را باز می‌کند.
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

_CACHE_NAME_PATTERN = re.compile(r'const CACHE_NAME = "faipco-shell-v[^"]*";')


def bump_app_cache_version() -> str:
    if not _FRONTEND_SW_PATH.exists():
        raise CacheBustError(f"فایل sw.js پیدا نشد: {_FRONTEND_SW_PATH}")

    content = _FRONTEND_SW_PATH.read_text(encoding="utf-8")
    new_version = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S")
    new_content, count = _CACHE_NAME_PATTERN.subn(
        f'const CACHE_NAME = "faipco-shell-v{new_version}";', content
    )
    if count == 0:
        raise CacheBustError("الگوی CACHE_NAME در sw.js پیدا نشد — ساختار فایل احتمالاً تغییر کرده.")

    # نوشتن Atomic — یا فایل کاملاً جایگزین می‌شود یا اصلاً دست‌نخورده می‌ماند
    tmp_path = _FRONTEND_SW_PATH.with_suffix(".js.tmp")
    tmp_path.write_text(new_content, encoding="utf-8")
    tmp_path.replace(_FRONTEND_SW_PATH)

    return new_version
