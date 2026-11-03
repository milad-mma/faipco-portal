"""
قواعد خالص امضای شخصی (سند مرجع بخش ۸.۱):
- بارگذاری: PNG/JPG/WEBP تا ۲ مگابایت، حداکثر ۴۰۰۰×۴۰۰۰ و ۸ مگاپیکسل؛ رسم: PNG شفاف از بوم مرورگر.
- decode در سرور، حذف metadata (ذخیره‌ی PNG تازه)، حذف اختیاری پس‌زمینه‌ی روشن، برش خودکار حاشیه، حفظ نسبت و کوچک‌سازی.
- SVG/HTML و هر چیز غیرتصویری رد می‌شود.
"""
from __future__ import annotations

import io

from PIL import Image, ImageOps, UnidentifiedImageError

MAX_UPLOAD_BYTES = 2 * 1024 * 1024
MAX_SIDE = 4000
MAX_PIXELS = 8_000_000
OUT_MAX = (900, 360)  # بزرگ‌ترین اندازه‌ی ذخیره‌شده (کیفیت کافی برای چاپ در عرض حدود ۵ سانتی‌متر)
PADDING = 8
ALLOWED = {"PNG", "JPEG", "WEBP"}
METHODS = ("draw", "upload")


class SignatureRulesError(ValueError):
    """خطای قابل نمایش."""


def _open(raw: bytes) -> Image.Image:
    if not raw:
        raise SignatureRulesError("تصویری دریافت نشد")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise SignatureRulesError("حجم تصویر امضا باید کمتر از ۲ مگابایت باشد")
    head = raw[:512].lstrip().lower()
    if head.startswith(b"<") or b"<svg" in head:
        raise SignatureRulesError("فقط تصویر PNG، JPG یا WEBP پذیرفته می‌شود")
    try:
        with Image.open(io.BytesIO(raw)) as probe:
            probe.verify()
        img = Image.open(io.BytesIO(raw))
        if img.format not in ALLOWED:
            raise SignatureRulesError("فقط تصویر PNG، JPG یا WEBP پذیرفته می‌شود")
        w, h = img.size
        if w > MAX_SIDE or h > MAX_SIDE or w * h > MAX_PIXELS:
            raise SignatureRulesError("ابعاد تصویر امضا خیلی بزرگ است (حداکثر ۴۰۰۰×۴۰۰۰ و ۸ مگاپیکسل)")
        img.load()
    except SignatureRulesError:
        raise
    except (UnidentifiedImageError, OSError, SyntaxError, Image.DecompressionBombError) as e:
        raise SignatureRulesError("فایل انتخاب‌شده تصویر معتبری نیست") from e
    return img


def _remove_light_background(rgba: Image.Image, threshold: int = 200) -> Image.Image:
    """پیکسل‌های روشن (کاغذ سفید/خاکستری) شفاف می‌شوند؛ لبه‌ها با شفافیت تدریجی نرم می‌مانند."""
    gray = rgba.convert("L")
    r, g, b, a = rgba.split()
    # روشن‌تر از آستانه → شفاف کامل؛ بین آستانه و ۶۰ واحد تیره‌تر → نیمه‌شفاف
    alpha = gray.point(lambda v: 0 if v >= threshold else (255 if v <= threshold - 60 else int((threshold - v) * 255 / 60)))
    alpha = Image.composite(alpha, Image.new("L", rgba.size, 0), a)
    return Image.merge("RGBA", (r, g, b, alpha))


def process_signature(raw: bytes, *, remove_background: bool) -> bytes:
    """خروجی: PNG شفاف برش‌خورده و بدون metadata."""
    img = _open(raw)
    img = ImageOps.exif_transpose(img)
    rgba = img.convert("RGBA")
    if remove_background:
        rgba = _remove_light_background(rgba)
    bbox = rgba.getchannel("A").point(lambda v: 255 if v > 16 else 0).getbbox()
    if not bbox:
        raise SignatureRulesError("امضایی در تصویر پیدا نشد؛ دوباره رسم یا تصویر دیگری انتخاب کنید")
    left, top, right, bottom = bbox
    if right - left < 20 or bottom - top < 10:
        raise SignatureRulesError("امضا خیلی کوچک است؛ بزرگ‌تر رسم کنید")
    rgba = rgba.crop((max(0, left - PADDING), max(0, top - PADDING),
                      min(rgba.width, right + PADDING), min(rgba.height, bottom + PADDING)))
    rgba.thumbnail(OUT_MAX, Image.Resampling.LANCZOS)
    out = io.BytesIO()
    clean = Image.new("RGBA", rgba.size)
    clean.putdata(list(rgba.getdata()))  # تصویر تازه بدون هیچ metadata
    clean.save(out, "PNG", optimize=True)
    return out.getvalue()
