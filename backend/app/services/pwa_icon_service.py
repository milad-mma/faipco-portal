"""
تولید آیکون‌های استاندارد PWA از یک تصویر آپلودشده - تا لوگو روی اندروید،
iOS و ویندوز نه خیلی کوچک باشد نه خیلی بزرگ (طبق درخواست کاربر).

مشکل قبلی: همان فایل خام برای همه‌جا استفاده می‌شد. اندروید آیکون maskable را
دایره/مربع‌گرد می‌بُرد (لوگوی تمام‌بوم لبه‌هایش حذف می‌شد)، iOS شفافیت را سیاه
می‌کند و گوشه‌ها را خودش گرد می‌کند، ویندوز آیکون "any" را کامل نشان می‌دهد.

نسخه‌ها:
  any-192 / any-512      ← purpose "any" (ویندوز، کروم دسکتاپ، iOS اگر apple نباشد)
  maskable-192 / -512    ← purpose "maskable" (اندروید): پس‌زمینه پر، لوگو در ناحیه امن
  apple-180              ← apple-touch-icon (iOS): بدون شفافیت، لوگو در ناحیه امن
  favicon-32 / -16       ← تب مرورگر (اگر favicon جداگانه آپلود نشده)

SVG با Pillow رَستر نمی‌شود؛ در آن حالت فایل خام برگردانده می‌شود (مثل قبل).
"""
from __future__ import annotations

import hashlib
import io
from functools import lru_cache

from PIL import Image, ImageColor

VARIANTS = {
    "any-192": ("any", 192),
    "any-512": ("any", 512),
    "maskable-192": ("maskable", 192),
    "maskable-512": ("maskable", 512),
    "apple-180": ("apple", 180),
    "favicon-32": ("any", 32),
    "favicon-16": ("any", 16),
}


def _parse_color(value: str, fallback=(255, 255, 255, 255)):
    if not value:
        return fallback
    try:
        rgba = ImageColor.getcolor(value, "RGBA")
        return rgba
    except ValueError:
        return fallback


def _fit_logo(source: Image.Image, canvas: int, occupy_percent: int) -> Image.Image:
    """لوگو را (با حفظ نسبت) طوری کوچک/بزرگ می‌کند که ضلع بزرگش occupy% بوم باشد."""
    target = max(1, int(canvas * occupy_percent / 100))
    w, h = source.size
    ratio = min(target / w, target / h)
    new_size = (max(1, int(w * ratio)), max(1, int(h * ratio)))
    return source.resize(new_size, Image.LANCZOS)


def _trim_transparent(img: Image.Image) -> Image.Image:
    """حاشیه کاملاً شفاف دور لوگو حذف می‌شود تا «اشغال بوم» واقعی باشد."""
    bbox = img.getchannel("A").getbbox()
    return img.crop(bbox) if bbox else img


@lru_cache(maxsize=64)
def _render_cached(digest: str, raw: bytes, variant: str, icon_scale: int, maskable_scale: int, bg: str, any_bg: str) -> bytes:
    kind, size = VARIANTS[variant]
    source = Image.open(io.BytesIO(raw)).convert("RGBA")
    source = _trim_transparent(source)
    if kind == "any":
        occupy = icon_scale
        background = _parse_color(any_bg, (0, 0, 0, 0)) if any_bg else (0, 0, 0, 0)
    else:
        occupy = maskable_scale
        background = _parse_color(bg)
        if kind == "apple":
            background = background[:3] + (255,)  # iOS: شفافیت ممنوع
    canvas = Image.new("RGBA", (size, size), background)
    logo = _fit_logo(source, size, occupy)
    offset = ((size - logo.width) // 2, (size - logo.height) // 2)
    canvas.alpha_composite(logo, offset)
    out = io.BytesIO()
    if kind == "apple":
        canvas.convert("RGB").save(out, format="PNG", optimize=True)
    else:
        canvas.save(out, format="PNG", optimize=True)
    return out.getvalue()


def render_icon(raw: bytes, content_type: str, variant: str, settings: dict) -> tuple[bytes, str]:
    """(bytes, media_type) - برای SVG یا خطای دیکود، فایل خام برمی‌گردد."""
    if variant not in VARIANTS:
        raise KeyError(variant)
    if content_type == "image/svg+xml":
        return raw, content_type
    digest = hashlib.sha1(raw).hexdigest()
    try:
        png = _render_cached(
            digest,
            raw,
            variant,
            int(settings.get("icon_scale", 100)),
            int(settings.get("maskable_scale", 66)),
            str(settings.get("background", "#FFFFFF")),
            str(settings.get("any_background", "")),
        )
    except Exception:  # noqa: BLE001 - تصویر خراب/ناشناخته: همان خام
        return raw, content_type
    return png, "image/png"
