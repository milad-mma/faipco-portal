"""
بررسی و پاک‌سازی فایل‌های آپلودی کاربر (مدارک بیمه تکمیلی).

- تصویر: با Pillow کامل باز و بررسی می‌شود (نه فقط چند بایت اول)، جهت EXIF اعمال و دوباره ذخیره
  می‌شود. ذخیره‌ی مجدد هر محتوای جاسازی‌شده (داده‌ی اضافه بعد از تصویر، اسکریپت، ...) و متادیتا
  (مختصات GPS، مدل گوشی، ...) را حذف می‌کند. تصاویر خیلی بزرگ (بمب تصویری) رد و تصاویر عادی حداکثر
  ۴۰۰۰ پیکسل می‌شوند. خروجی JPEG، یا PNG برای تصویر شفاف.
- PDF: ساختار پایه (سربرگ و %%EOF) بررسی و PDF رمزدار یا دارای اجزای فعال (جاوااسکریپت، اجرای برنامه،
  فایل پیوست، فرم XFA، محتوای چندرسانه‌ای) رد می‌شود. بررسی روی بایت‌های خام است؛ نام‌هایی که داخل
  جریان‌های فشرده پنهان شده باشند دیده نمی‌شوند (اسکن آنتی‌ویروس بخشی از این لایه نیست).
- نام فایل: کاراکترهای کنترلی، جداکننده‌ی مسیر و کاراکترهای خطرناک هدر حذف و پسوند با نوع واقعی یکی می‌شود.

خطای قابل نمایش به کاربر با DocumentRejected (پیام فارسی) اعلام می‌شود.
"""
from __future__ import annotations

import io
import re
import unicodedata
import warnings

MAX_IMAGE_PIXELS = 50_000_000  # بیشتر از این (حدود ۷۰۰۰×۷۰۰۰) بمب تصویری شمرده می‌شود
MAX_IMAGE_SIDE = 4000  # طول بزرگ‌ترین ضلع تصویر ذخیره‌شده
JPEG_QUALITY = 88

# نام‌های PDF که یعنی محتوای فعال یا فایل جاسازی‌شده
_PDF_DANGEROUS_NAMES = {b"JavaScript", b"JS", b"Launch", b"EmbeddedFile", b"EmbeddedFiles", b"RichMedia", b"XFA"}
_PDF_NAME_RE = re.compile(rb"/([A-Za-z0-9#_.\-]+)")
_EXT = {"image/jpeg": ".jpg", "image/png": ".png", "application/pdf": ".pdf"}


class DocumentRejected(ValueError):
    """فایل پذیرفته نشد؛ متن استثنا پیام فارسی برای کاربر است."""


def _decode_pdf_name(raw: bytes) -> bytes:
    """نام PDF با کدگذاری #xx (مثل /J#61vaScript) را به شکل واقعی برمی‌گرداند."""
    return re.sub(rb"#([0-9A-Fa-f]{2})", lambda m: bytes([int(m.group(1), 16)]), raw)


_PDF_STREAM_RE = re.compile(rb"stream\r?\n.*?endstream", re.S)


def _strip_pdf_streams(content: bytes) -> bytes:
    """بدنه‌ی همه‌ی stream های PDF را حذف می‌کند تا فقط ساختار (دیکشنری‌ها و اشیا) باقی بماند."""
    return _PDF_STREAM_RE.sub(b"stream endstream", content)


def check_pdf(content: bytes) -> bytes:
    """PDF را بررسی می‌کند و همان بایت‌ها را برمی‌گرداند؛ PDF ناقص، رمزدار یا دارای محتوای فعال → DocumentRejected."""
    if not content.startswith(b"%PDF-"):
        raise DocumentRejected("فایل PDF معتبر نیست.")
    if b"%%EOF" not in content[-65536:]:
        raise DocumentRejected("فایل PDF ناقص یا خراب است.")
    # نام‌ها فقط در ساختار PDF (بیرون از بدنه‌ی stream ها) جست‌وجو می‌شوند. بدنه‌ی stream (تصویر اسکن، فونت، محتوای
    # فشرده) داده‌ی باینری است و الگوهایی مثل «/JS» به‌طور تصادفی در آن پیدا می‌شوند — قبلاً حدود ۱۵٪ PDF های اسکن‌شده‌ی
    # چندمگابایتی به اشتباه رد می‌شدند. نام‌های داخل stream فشرده از قبل هم دیده نمی‌شدند، پس تشخیص واقعی کم نمی‌شود.
    for match in _PDF_NAME_RE.finditer(_strip_pdf_streams(content)):
        name = _decode_pdf_name(match.group(1))
        if name == b"Encrypt":
            raise DocumentRejected("فایل PDF رمزدار پذیرفته نمی‌شود.")
        if name in _PDF_DANGEROUS_NAMES:
            raise DocumentRejected(
                "این فایل PDF محتوای فعال (مثل اسکریپت یا فایل پیوست) دارد و پذیرفته نمی‌شود؛ لطفاً تصویر یا PDF ساده (اسکن) بفرستید."
            )
    return content


def reencode_image(content: bytes) -> tuple[bytes, str]:
    """
    تصویر را کامل باز، بررسی و دوباره ذخیره می‌کند. خروجی: (بایت‌های جدید، نوع MIME).
    تصویر خراب، ناشناخته یا بیش از حد بزرگ → DocumentRejected.
    """
    from PIL import Image, ImageOps

    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        previous_limit = Image.MAX_IMAGE_PIXELS
        Image.MAX_IMAGE_PIXELS = MAX_IMAGE_PIXELS
        try:
            try:
                with Image.open(io.BytesIO(content)) as probe:
                    probe.verify()  # ساختار کامل فایل
                img = Image.open(io.BytesIO(content))
                img.load()
            except (Image.DecompressionBombError, Image.DecompressionBombWarning):
                raise DocumentRejected("ابعاد تصویر بیش از حد بزرگ است.")
            except Exception:  # noqa: BLE001 - هر خطای خواندن یعنی تصویر معتبر نیست
                raise DocumentRejected("فایل تصویری معتبر نیست یا خراب است.")
        finally:
            Image.MAX_IMAGE_PIXELS = previous_limit

    try:
        if getattr(img, "n_frames", 1) > 1:
            img.seek(0)  # تصویر متحرک: فقط فریم اول
        img = ImageOps.exif_transpose(img)  # چرخش عکس گوشی قبل از حذف EXIF
        img.thumbnail((MAX_IMAGE_SIDE, MAX_IMAGE_SIDE))
        has_alpha = img.mode in ("RGBA", "LA") or (img.mode == "P" and "transparency" in img.info)
        out = io.BytesIO()
        if has_alpha:
            img.convert("RGBA").save(out, format="PNG", optimize=True)
            return out.getvalue(), "image/png"
        img.convert("RGB").save(out, format="JPEG", quality=JPEG_QUALITY, optimize=True)
        return out.getvalue(), "image/jpeg"
    except DocumentRejected:
        raise
    except Exception:  # noqa: BLE001
        raise DocumentRejected("پردازش تصویر ممکن نشد؛ لطفاً فایل دیگری انتخاب کنید.")


def sanitize_document(content: bytes, detected_type: str) -> tuple[bytes, str]:
    """نوع تشخیص‌داده‌شده از بایت‌ها → بررسی/پاک‌سازی. خروجی: (بایت‌های نهایی، نوع MIME نهایی)."""
    if detected_type == "application/pdf":
        return check_pdf(content), "application/pdf"
    if detected_type.startswith("image/"):
        return reencode_image(content)
    raise DocumentRejected("نوع فایل پذیرفته نمی‌شود.")


def sanitize_file_name(name: str | None, content_type: str) -> str:
    """
    نام فایل امن برای ذخیره و هدر دانلود: حذف کاراکترهای کنترلی/نامرئی، جداکننده‌ی مسیر و کاراکترهای
    " < > : * ? | ؛ حداکثر ۱۰۰ کاراکتر؛ پسوند مطابق نوع واقعی فایل.
    """
    text = unicodedata.normalize("NFC", str(name or ""))
    # نیم‌فاصله (ZWNJ) در نام فارسی می‌ماند؛ بقیه‌ی کاراکترهای کنترلی/نامرئی (مثل RLO که پسوند را وارونه نشان می‌دهد) حذف
    text = "".join(ch for ch in text if ch == "\u200c" or unicodedata.category(ch)[0] != "C")
    text = re.sub(r'[\\/"<>:*?|;\x7f]', "_", text).strip(" .")
    stem = text.rsplit(".", 1)[0] if "." in text else text
    stem = re.sub(r"\s+", " ", stem).strip(" ._")[:100] or "document"
    return stem + _EXT.get(content_type, "")


def sniff_content_type(content: bytes) -> str:
    """
    نوع فایل را از بایت‌های ابتدایی (magic number) تشخیص می‌دهد و MIME آن را
    برمی‌گرداند. برای فرمت‌های ناشناخته "application/octet-stream" برمی‌گردد
    که در فهرست مجاز نیست و آپلود را رد می‌کند.
    """
    head = content[:16]
    if head.startswith(b"%PDF"):
        return "application/pdf"
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if head.startswith(b"RIFF") and content[8:12] == b"WEBP":
        return "image/webp"
    if head.startswith(b"BM"):
        return "image/bmp"
    if head.startswith((b"II*\x00", b"MM\x00*")):
        return "image/tiff"
    return "application/octet-stream"
