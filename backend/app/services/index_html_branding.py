"""
نوشتن برندینگ (عنوان <title> و apple-mobile-web-app-title) داخل خودِ فایل frontend/dist/index.html.

چرا فقط سرو پویا کافی نبود: Service Worker (Workbox) فایل /index.html را
پیش‌کش (precache) می‌کند و برای ناوبری‌های بعدی و اپ نصب‌شده، همان نسخه
کش‌شده را برمی‌گرداند - نه پاسخ پویای Backend. اگر خودِ فایل روی دیسک عنوان
درست را داشته باشد، هر مسیری (استاتیک، SW، پویا) عنوان درست را می‌دهد.

چه زمانی: هنگام ذخیره برندینگ از پنل، و در شروع سرویس (چون install.sh
فرانت را از نو Build می‌کند و فایل تازه دوباره عنوان ثابت زمان Build را دارد).
"""
from __future__ import annotations

import html
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

INDEX_HTML_PATH = Path(__file__).resolve().parent.parent.parent.parent / "frontend" / "dist" / "index.html"

# الگوهای تگ title و مقدار content در meta عنوان اپ iOS
_TITLE_RE = re.compile(r"<title>.*?</title>", re.DOTALL)
_APPLE_TITLE_RE = re.compile(r'(<meta\s+name="apple-mobile-web-app-title"\s+content=")[^"]*(")')


def apply_branding_to_html(source: str, browser_title: str, short_name: str | None = None) -> str:
    """
    ورودی: متن HTML، عنوان مرورگر و نام کوتاه اختیاری.
    خروجی: HTML با <title> و (در صورت وجود short_name) عنوان اپ iOS جایگزین‌شده (escape شده).
    """
    result = _TITLE_RE.sub(f"<title>{html.escape(browser_title)}</title>", source, count=1)
    if short_name:
        result = _APPLE_TITLE_RE.sub(lambda m: f"{m.group(1)}{html.escape(short_name)}{m.group(2)}", result, count=1)
    return result


def write_index_html_branding(browser_title: str, short_name: str | None = None) -> bool:
    """فایل dist/index.html را در جا به‌روز می‌کند. True = نوشته شد. خطا فقط لاگ می‌شود."""
    try:
        # اگر فرانت Build نشده یا محتوا تغییری نکرده، چیزی نوشته نمی‌شود
        if not INDEX_HTML_PATH.exists():
            return False
        source = INDEX_HTML_PATH.read_text(encoding="utf-8")
        updated = apply_branding_to_html(source, browser_title, short_name)
        if updated == source:
            return False
        INDEX_HTML_PATH.write_text(updated, encoding="utf-8")
        logger.info("عنوان برندینگ داخل %s نوشته شد", INDEX_HTML_PATH)
        return True
    except OSError as e:
        logger.warning("نوشتن برندینگ در index.html ناموفق بود (%s): %s", INDEX_HTML_PATH, e)
        return False
