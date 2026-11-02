"""
قواعد خالص عکس پرسنلی — آماده‌سازی عکس دقیقاً مطابق کاراوب (بررسی ۱۴۰۵/۰۸/۱۱، claude/profile-photo-upload.md):

- Img: کاراوب خود فایل آپلودی را بایت به بایت ذخیره می‌کند و فقط عکس زیر ۱۰۰ کیلوبایت را می‌پذیرد.
  اینجا اگر فایل JPEG/PNG و زیر سقف باشد (و چرخش EXIF نداشته باشد) همان بایت‌ها نگه داشته می‌شود؛
  وگرنه به JPEG کوچک‌تر تبدیل می‌شود تا پرسنل خودش درگیر کم کردن حجم نشود.
- ThumbnailImg: GIF89a ‏۸۸×۸۸ بدون حفظ نسبت (کشیده)، پالت ثابت halftone ‏GDI+ ‏(۶ سطح قرمز × ۷ سبز × ۶ آبی
  = ۲۵۲ رنگ + ۴ مشکی) و transparency index = 252 — همان چیزی که System.Drawing کاراوب می‌سازد.
"""
from __future__ import annotations

import io

from PIL import Image, ImageOps, UnidentifiedImageError

KARA_MAX_BYTES = 100_000  # «حجم عکس باید کمتر از 100 کیلوبایت باشد» (پیام کاراوب)
MAX_INPUT_BYTES = 15 * 1024 * 1024  # فایل ورودی پرسنل (قبل از کوچک‌سازی)
MIN_SIDE_PX = 80
MAX_SIDE_PX = 800  # بلندترین ضلع هنگام تبدیل
THUMB_SIZE = (88, 88)
THUMB_TRANSPARENT_INDEX = 252
ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP", "GIF", "BMP"}
_KEEP_AS_IS_FORMATS = {"JPEG", "PNG"}  # فرمت‌هایی که کاراوب هم ذخیره کرده بود

_R_LEVELS = (0x00, 0x33, 0x66, 0x99, 0xCC, 0xFF)
_G_LEVELS = (0x00, 0x2B, 0x55, 0x80, 0xAA, 0xD5, 0xFF)
_B_LEVELS = (0x00, 0x33, 0x66, 0x99, 0xCC, 0xFF)


class PhotoRulesError(ValueError):
    """خطای قابل نمایش به پرسنل."""


def halftone_palette() -> list[int]:
    """پالت ۲۵۶ رنگی GDI+ به همان ترتیب فایل‌های کاراوب: قرمز بیرونی، سبز میانی، آبی درونی؛ ۴ خانه‌ی آخر مشکی."""
    pal: list[int] = []
    for r in _R_LEVELS:
        for g in _G_LEVELS:
            for b in _B_LEVELS:
                pal += [r, g, b]
    pal += [0, 0, 0] * (256 - len(pal) // 3)
    return pal


def _open(raw: bytes) -> Image.Image:
    if not raw:
        raise PhotoRulesError("فایلی انتخاب نشده است")
    if len(raw) > MAX_INPUT_BYTES:
        raise PhotoRulesError(f"حجم فایل باید کمتر از {MAX_INPUT_BYTES // (1024 * 1024)} مگابایت باشد")
    try:
        with Image.open(io.BytesIO(raw)) as probe:
            probe.verify()
        image = Image.open(io.BytesIO(raw))
        image.load()
    except (UnidentifiedImageError, OSError, Image.DecompressionBombError, SyntaxError) as e:
        raise PhotoRulesError("فایل انتخاب‌شده عکس معتبری نیست (JPEG یا PNG بفرستید)") from e
    if image.format not in ALLOWED_FORMATS:
        raise PhotoRulesError("فرمت عکس پشتیبانی نمی‌شود (JPEG یا PNG بفرستید)")
    if min(image.size) < MIN_SIDE_PX:
        raise PhotoRulesError(f"عکس خیلی کوچک است (حداقل {MIN_SIDE_PX} پیکسل در هر ضلع)")
    return image


def _to_rgb(image: Image.Image) -> Image.Image:
    """چرخش EXIF اعمال و پس‌زمینه‌ی شفاف سفید می‌شود."""
    image = ImageOps.exif_transpose(image)
    if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
        rgba = image.convert("RGBA")
        canvas = Image.new("RGB", rgba.size, (255, 255, 255))
        canvas.paste(rgba, mask=rgba.split()[-1])
        return canvas
    return image.convert("RGB")


def _needs_rotation(image: Image.Image) -> bool:
    try:
        return int(image.getexif().get(0x0112, 1) or 1) != 1
    except Exception:  # noqa: BLE001
        return False


def _encode_jpeg(rgb: Image.Image) -> bytes:
    """JPEG زیر سقف کاراوب: اول کیفیت کم می‌شود، بعد ابعاد."""
    img = rgb
    if max(img.size) > MAX_SIDE_PX:
        img = img.copy()
        img.thumbnail((MAX_SIDE_PX, MAX_SIDE_PX), Image.Resampling.LANCZOS)
    while True:
        for quality in (90, 85, 80, 75, 70, 65, 60):
            buf = io.BytesIO()
            img.save(buf, "JPEG", quality=quality, optimize=True)
            if buf.tell() < KARA_MAX_BYTES:
                return buf.getvalue()
        if max(img.size) <= 200:
            raise PhotoRulesError("کم کردن حجم عکس ممکن نشد؛ عکس دیگری انتخاب کنید")
        img = img.resize((int(img.width * 0.8), int(img.height * 0.8)), Image.Resampling.LANCZOS)


def make_thumbnail(rgb: Image.Image) -> bytes:
    """GIF ‏۸۸×۸۸ مثل کاراوب (کشیده، پالت halftone، شفافیت روی خانه‌ی ۲۵۲)."""
    small = rgb.resize(THUMB_SIZE, Image.Resampling.BICUBIC)
    pal_img = Image.new("P", (1, 1))
    pal_img.putpalette(halftone_palette())
    # فقط ۲۵۲ رنگ اول برای نگاشت؛ خانه‌های مشکی آخر (از جمله خانه‌ی شفاف) هرگز انتخاب نمی‌شوند
    quant_pal = Image.new("P", (1, 1))
    quant_pal.putpalette(halftone_palette()[: 252 * 3] + halftone_palette()[: 3] * 4)
    q = small.quantize(palette=quant_pal, dither=Image.Dither.FLOYDSTEINBERG)
    q.putpalette(halftone_palette())
    buf = io.BytesIO()
    q.save(buf, "GIF", transparency=THUMB_TRANSPARENT_INDEX, optimize=False, interlace=False)
    data = bytearray(buf.getvalue())
    # بایت بسته‌ی Logical Screen مثل GDI+: پالت سراسری، وضوح رنگ ۸ بیت، ۲۵۶ خانه (0xF7)
    data[10] = 0xF7
    return bytes(data)


def prepare_upload(raw: bytes) -> tuple[bytes, bytes]:
    """ورودی: فایل خام پرسنل. خروجی: (بایت‌های Img برای کاراوب، بایت‌های ThumbnailImg)."""
    image = _open(raw)
    keep_raw = image.format in _KEEP_AS_IS_FORMATS and len(raw) < KARA_MAX_BYTES and not _needs_rotation(image)
    rgb = _to_rgb(image)
    main = raw if keep_raw else _encode_jpeg(rgb)
    return main, make_thumbnail(rgb)


def image_media_type(data: bytes | None) -> str:
    if not data:
        return "application/octet-stream"
    if data[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return "image/png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return "image/gif"
