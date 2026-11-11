"""
سرویس «پاک‌کردن کش اپلیکیشن برای همه کاربران».

نکته پلتفرمی مهم: هیچ API وبی وجود ندارد که سرور بتواند از راه دور کش
مرورگر یک کاربر را پاک کند. تنها راه واقعی و قانونی این است که خودِ فایل
sw.js از نظر بایتی تغییر کند — مرورگر هر کاربر، هر بار که به سایت سر می‌زند،
محتوای sw.js را دوباره می‌گیرد و اگر با نسخه نصب‌شده فرق داشته باشد، نسخه
جدید را نصب می‌کند؛ Workbox (که این پروژه با آن ساخته شده)، در فاز
activate خودش، هر Cache قدیمی مرتبط با نسخه Precache قبلی را پاک می‌کند.

روش کار، مستقل از جزئیات داخلی Workbox (که نسخه‌بندی Cache را با
`self.__WB_MANIFEST` انجام می‌دهد): یک خط Comment با برچسب‌زمانی تازه به انتهای
sw.js اضافه/به‌روزرسانی می‌شود. همین تغییرِ حتی یک بایت، برای مرورگر کافی است تا
sw.js را «تغییر‌کرده» تشخیص دهد و چرخه عادی نصب/فعال‌سازی نسخه جدید (که
Workbox داخلش Cache قدیمی را پاک می‌کند) را شروع کند.
"""
from __future__ import annotations

import os
import re
import stat
import tempfile
from datetime import datetime, timezone
from pathlib import Path


class CacheBustError(Exception):
    """خطا وقتی فایل sw.js پیدا نشود."""
    pass


# frontend/dist در کنار backend/ قرار دارد (هر دو زیر ریشه پروژه)
_FRONTEND_SW_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent / "frontend" / "dist" / "sw.js"
)

# خط برچسب cache-bust در انتهای فایل (نسخه‌های قدیمی ۱۴ رقمی نیز خوانده می‌شوند)
_BUST_MARKER_PATTERN = re.compile(r"\n// cache-bust: [^\n]*\n?$")
_BUST_VERSION_PATTERN = re.compile(r"\n// cache-bust: (\d{14}(?:\d{6})?)\n?$")


def deployed_cache_refresh() -> str | None:
    """The cache-refresh marker on the *live* SW. Replayed on WS reconnect."""
    try:
        match = _BUST_VERSION_PATTERN.search(_FRONTEND_SW_PATH.read_text(encoding="utf-8"))
        return match.group(1) if match else None
    except (OSError, UnicodeError):
        return None


def bump_app_cache_version() -> str:
    """
    برچسب cache-bust انتهای frontend/dist/sw.js را با زمان فعلی جایگزین/اضافه می‌کند.
    خروجی: شناسه یکتای نوسازی (UTC تا دقت میکروثانیه). خطا: CacheBustError اگر sw.js نباشد.
    """
    if not _FRONTEND_SW_PATH.exists():
        raise CacheBustError(f"فایل sw.js پیدا نشد: {_FRONTEND_SW_PATH}")

    content = _FRONTEND_SW_PATH.read_text(encoding="utf-8")
    new_version = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    marker = f"\n// cache-bust: {new_version}\n"

    # اگر از قبل یک برچسب cache-bust در انتهای فایل بود، جایگزینش می‌کنیم؛
    # وگرنه یکی جدید اضافه می‌کنیم — تا فایل با هر بار کلیک بی‌نهایت بزرگ نشود.
    if _BUST_MARKER_PATTERN.search(content):
        new_content = _BUST_MARKER_PATTERN.sub(marker, content)
    else:
        new_content = content.rstrip("\n") + "\n" + marker.lstrip("\n")

    # نوشتن Atomic با فایل موقت مستقل (دو درخواست همزمان روی یک .tmp نمی‌نویسند).
    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=_FRONTEND_SW_PATH.parent,
            prefix=".sw-refresh-", suffix=".tmp", delete=False,
        ) as temp:
            tmp_path = Path(temp.name)
            temp.write(new_content)
        os.chmod(tmp_path, stat.S_IMODE(_FRONTEND_SW_PATH.stat().st_mode))
        os.replace(tmp_path, _FRONTEND_SW_PATH)
    finally:
        if tmp_path is not None:
            tmp_path.unlink(missing_ok=True)

    return new_version
