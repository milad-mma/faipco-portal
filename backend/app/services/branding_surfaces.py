"""
برندینگ به تفکیک «جای نمایش» (Surface): لوگو، اندازه، مقیاس، قاب، متن‌ها،
اندازه فونت و رنگ‌ها برای هر جا به‌صورت مستقل؛ به‌علاوه تنظیمات تولید آیکون PWA.

جای‌های نمایش: splash (اسپلش‌اسکرین)، login (صفحه ورود)، auth (فراموشی/بازیابی
رمز)، sidebar (نوار بالای پنل ادمین)، profile (پنل کاربری).

ذخیره‌سازی: یک ردیف JSON در system_settings (کلید branding_surfaces) که فقط
مقادیرِ تغییرداده‌شده را نگه می‌دارد؛ خواندن همیشه روی DEFAULTS ادغام می‌شود،
پس تا وقتی ادمین چیزی را عوض نکرده، ظاهر همان پیش‌فرض‌هاست.
لوگوی اختصاصی هر Surface در کلیدهای surface_logo_<name>_data/_content_type.

پیش‌فرض‌ها (DEFAULTS) با ظاهر پیش‌فرض فرانت‌اند یکسان‌اند.
"""
from __future__ import annotations

import json
from copy import deepcopy

# نام همه جای‌های نمایش پشتیبانی‌شده
SURFACES = ("splash", "login", "auth", "sidebar", "profile")

# ساختار هر Surface (همه اعداد پیکسل، مقیاس/فونت عدد صحیح):
#   logo_source: "default" | "custom" | "none"
#   default_logo: "app_logo" | "app_logo_small"  ← وقتی logo_source=default
#   logo_size_mobile / logo_size_desktop، logo_scale (درصد، ۲۵..۳۰۰)
#   frame: "none" | "circle" | "rounded"، frame_color، frame_padding
#   title_size_mobile/desktop، subtitle_size_mobile/desktop، title_color، subtitle_color
#   title_weight (400..900)
#   background: رشته CSS (رنگ یا gradient) - خالی = بدون تغییر/پیش‌فرض تم
#   show_title / show_subtitle
_LOGIN_LIKE = {
    "logo_source": "default",
    "default_logo": "app_logo_small",
    "logo_size_mobile": 42,
    "logo_size_desktop": 48,
    "logo_scale": 100,
    "frame": "circle",
    "frame_color": "#FFFFFF",
    "frame_padding": 14,
    "title_size_mobile": 15,
    "title_size_desktop": 16,
    "subtitle_size_mobile": 11,
    "subtitle_size_desktop": 11,
    "title_color": "#FFFFFF",
    "subtitle_color": "rgba(255,255,255,0.85)",
    "title_weight": 800,
    "background": "linear-gradient(110deg, #3476ad, #2b91a5)",
    "show_title": True,
    "show_subtitle": True,
}

# مقادیر پیش‌فرض هر جای نمایش؛ login و auth ظاهر یکسان دارند
DEFAULTS: dict[str, dict] = {
    "splash": {
        "logo_source": "default",
        "default_logo": "app_logo",
        "logo_size_mobile": 120,
        "logo_size_desktop": 150,
        "logo_scale": 100,
        "frame": "none",
        "frame_color": "#FFFFFF",
        "frame_padding": 0,
        "title_size_mobile": 16,
        "title_size_desktop": 16,
        "subtitle_size_mobile": 14,
        "subtitle_size_desktop": 14,
        "title_color": "#000000",
        "subtitle_color": "#6B7280",
        "title_weight": 700,
        "background": "#FFFFFF",
        "show_title": True,
        "show_subtitle": True,
    },
    "login": deepcopy(_LOGIN_LIKE),
    "auth": deepcopy(_LOGIN_LIKE),
    "sidebar": {
        "logo_source": "default",
        "default_logo": "app_logo_small",
        "logo_size_mobile": 40,
        "logo_size_desktop": 40,
        "logo_scale": 100,
        "frame": "none",
        "frame_color": "#FFFFFF",
        "frame_padding": 0,
        "title_size_mobile": 16,
        "title_size_desktop": 16,
        "subtitle_size_mobile": 12,
        "subtitle_size_desktop": 12,
        "title_color": "",  # خالی = رنگ اصلی تم (primary)
        "subtitle_color": "",
        "title_weight": 700,
        "background": "",
        "show_title": True,
        "show_subtitle": False,
    },
    "profile": {
        "logo_source": "default",
        "default_logo": "app_logo",
        "logo_size_mobile": 84,
        "logo_size_desktop": 84,
        "logo_scale": 100,
        "frame": "circle",
        "frame_color": "#FFFFFF",
        "frame_padding": 24,
        "title_size_mobile": 16,
        "title_size_desktop": 16,
        "subtitle_size_mobile": 14,
        "subtitle_size_desktop": 14,
        "title_color": "",
        "subtitle_color": "",
        "title_weight": 700,
        "background": "linear-gradient(135deg, #185E95 0%, #2E84AA 100%)",
        "show_title": True,
        "show_subtitle": True,
    },
}

# قواعد اعتبارسنجی کلیدها: بازه اعداد، مقادیر مجاز enum، حداکثر طول رشته‌ها و کلیدهای بولی
_INT_RANGES = {
    "logo_size_mobile": (8, 400),
    "logo_size_desktop": (8, 400),
    "logo_scale": (25, 300),
    "frame_padding": (0, 80),
    "title_size_mobile": (8, 64),
    "title_size_desktop": (8, 64),
    "subtitle_size_mobile": (8, 48),
    "subtitle_size_desktop": (8, 48),
    "title_weight": (300, 900),
}
_ENUMS = {
    "logo_source": {"default", "custom", "none"},
    "default_logo": {"app_logo", "app_logo_small"},
    "frame": {"none", "circle", "rounded"},
}
_STR_MAX = {"frame_color": 64, "title_color": 64, "subtitle_color": 64, "background": 300}
_BOOLS = {"show_title", "show_subtitle"}

# آیکون PWA - تولید نسخه‌های استاندارد از یک تصویر مربعی
PWA_ICON_DEFAULTS = {
    "icon_scale": 100,  # درصد اشغال بوم در آیکون "any" (ویندوز/کروم دسکتاپ)
    "maskable_scale": 66,  # درصد اشغال بوم در maskable (اندروید) و apple (iOS): ناحیه امن ≈ ۸۰٪ قطر
    "background": "#FFFFFF",  # پس‌زمینه maskable/apple (iOS شفافیت را سیاه می‌کند)
    "any_background": "",  # خالی = شفاف
}
_PWA_INT_RANGES = {"icon_scale": (30, 100), "maskable_scale": (30, 90)}  # بازه مجاز درصدهای آیکون PWA


def merged_surfaces(stored_json: str | None) -> dict[str, dict]:
    """ورودی: JSON ذخیره‌شده (یا None). خروجی: تنظیمات کامل همه Surface ها = DEFAULTS با اعمال مقادیر ذخیره‌شده."""
    result = deepcopy(DEFAULTS)
    # JSON خراب یا غیر dict نادیده گرفته می‌شود و پیش‌فرض‌ها برمی‌گردند
    if not stored_json:
        return result
    try:
        stored = json.loads(stored_json)
    except (ValueError, TypeError):
        return result
    if not isinstance(stored, dict):
        return result
    # فقط Surface ها و کلیدهای شناخته‌شده روی پیش‌فرض ادغام می‌شوند
    for surface, values in stored.items():
        if surface in result and isinstance(values, dict):
            result[surface].update({k: v for k, v in values.items() if k in result[surface]})
    return result


def sanitize_surface_patch(surface: str, patch: dict) -> dict:
    """
    ورودی: نام Surface و dict تغییرات. خروجی: فقط کلیدهای شناخته‌شده با مقدار معتبر
    (اعداد به بازه مجاز محدود می‌شوند؛ مقدار نامعتبر نادیده گرفته می‌شود).
    خطا: ValueError برای Surface نامعتبر.
    """
    if surface not in DEFAULTS:
        raise ValueError("جای نمایش نامعتبر است")
    clean: dict = {}
    # بررسی هر کلید بر اساس نوعش
    for key, value in patch.items():
        if key not in DEFAULTS[surface]:
            continue
        if key in _INT_RANGES:
            try:
                iv = int(value)
            except (TypeError, ValueError):
                continue
            lo, hi = _INT_RANGES[key]
            clean[key] = max(lo, min(hi, iv))  # محدود کردن به بازه
        elif key in _ENUMS:
            if value in _ENUMS[key]:
                clean[key] = value
        elif key in _BOOLS:
            clean[key] = bool(value)
        elif key in _STR_MAX:
            if value is None:
                clean[key] = ""
            elif isinstance(value, str) and len(value) <= _STR_MAX[key] and _safe_css_value(value):
                clean[key] = value.strip()
    return clean


def _safe_css_value(value: str) -> bool:
    """True اگر رشته رنگ/گرادیان CSS بدون url()، expression و کاراکترهای خطرناک باشد (جلوگیری از XSS از طریق style)."""
    lowered = value.lower()
    if any(bad in lowered for bad in ("url(", "expression", "javascript", "<", ">", ";", "{", "}")):
        return False
    return True


def merged_pwa_icon(stored_json: str | None) -> dict:
    """ورودی: JSON ذخیره‌شده (یا None). خروجی: تنظیمات کامل آیکون PWA = پیش‌فرض‌ها با اعمال مقادیر معتبر ذخیره‌شده."""
    result = dict(PWA_ICON_DEFAULTS)
    if not stored_json:
        return result
    try:
        stored = json.loads(stored_json)
    except (ValueError, TypeError):
        return result
    if isinstance(stored, dict):
        result.update(sanitize_pwa_patch(stored))
    return result


def sanitize_pwa_patch(patch: dict) -> dict:
    """ورودی: dict تغییرات آیکون PWA. خروجی: فقط کلیدهای معتبر (درصدها محدود به بازه، رنگ‌ها امن)."""
    clean: dict = {}
    for key, value in patch.items():
        if key in _PWA_INT_RANGES:
            try:
                iv = int(value)
            except (TypeError, ValueError):
                continue
            lo, hi = _PWA_INT_RANGES[key]
            clean[key] = max(lo, min(hi, iv))
        elif key in ("background", "any_background"):
            if value is None:
                clean[key] = ""
            elif isinstance(value, str) and len(value) <= 32 and _safe_css_value(value):
                clean[key] = value.strip()
    return clean
