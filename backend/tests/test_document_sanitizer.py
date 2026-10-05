"""تست‌های بررسی و پاک‌سازی فایل‌های آپلودی (app/core/document_sanitizer.py)."""
import io

import pytest

PIL = pytest.importorskip("PIL")

from PIL import Image  # noqa: E402

from app.core.document_sanitizer import (  # noqa: E402
    DocumentRejected,
    check_pdf,
    reencode_image,
    sanitize_document,
    sanitize_file_name,
)


def _jpeg_with_gps_and_payload():
    """JPEG با EXIF (شامل GPS) و داده‌ی اضافه (شبیه اسکریپت) بعد از پایان تصویر."""
    img = Image.new("RGB", (60, 40), (200, 10, 10))
    exif = Image.Exif()
    exif[0x010F] = "PhoneMaker"  # Make
    exif[0x8825] = {1: "N", 2: (35.0, 41.0, 0.0)}  # GPSInfo
    buf = io.BytesIO()
    img.save(buf, format="JPEG", exif=exif)
    return buf.getvalue() + b"<script>alert(1)</script>"


def test_image_is_reencoded_and_metadata_removed():
    raw = _jpeg_with_gps_and_payload()
    out, mime = reencode_image(raw)
    assert mime == "image/jpeg"
    assert b"<script>" not in out and b"PhoneMaker" not in out
    with Image.open(io.BytesIO(out)) as img:
        assert img.size == (60, 40)
        assert not img.getexif()


def test_transparent_png_stays_png_and_large_image_is_resized():
    img = Image.new("RGBA", (5000, 100), (0, 0, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    out, mime = reencode_image(buf.getvalue())
    assert mime == "image/png"
    with Image.open(io.BytesIO(out)) as res:
        assert max(res.size) == 4000


def test_fake_image_and_bomb_rejected():
    # فقط دو بایت «BM» (امضای BMP) و بقیه متن دلخواه
    with pytest.raises(DocumentRejected):
        reencode_image(b"BM" + b"not really an image" * 10)
    # بمب تصویری: سربرگ PNG با ابعاد خیلی بزرگ
    big = Image.new("1", (12000, 12000))
    buf = io.BytesIO()
    big.save(buf, format="PNG")
    with pytest.raises(DocumentRejected):
        reencode_image(buf.getvalue())


def test_pdf_checks():
    ok = b"%PDF-1.4\n1 0 obj << /Type /Catalog >> endobj\ntrailer << /Root 1 0 R >>\n%%EOF\n"
    assert check_pdf(ok) == ok
    with pytest.raises(DocumentRejected):
        check_pdf(b"%PDF-1.4\n<< /OpenAction << /S /JavaScript /JS (app.alert(1)) >> >>\n%%EOF")
    with pytest.raises(DocumentRejected):
        check_pdf(b"%PDF-1.4\n<< /S /J#61vaScript >>\n%%EOF")  # نام کدگذاری‌شده
    with pytest.raises(DocumentRejected):
        check_pdf(b"%PDF-1.7\n<< /Encrypt 5 0 R >>\n%%EOF")
    with pytest.raises(DocumentRejected):
        check_pdf(b"%PDF-1.7\n<< /Type /Catalog >>")  # بدون %%EOF
    with pytest.raises(DocumentRejected):
        sanitize_document(b"MZ\x90\x00", "application/octet-stream")


def test_sanitize_file_name():
    assert sanitize_file_name('..\\..\\evil"; x.exe', "image/jpeg") == "evil__ x.jpg"
    assert sanitize_file_name("مدرک‮jpg.exe", "application/pdf") == "مدرکjpg.pdf"
    assert sanitize_file_name("شناسنامه‌پدر.PNG", "image/png") == "شناسنامه‌پدر.png"
    assert sanitize_file_name("", "image/jpeg") == "document.jpg"
    assert sanitize_file_name("a\r\nb.pdf", "application/pdf") == "ab.pdf"


def test_pdf_random_streams_not_rejected():
    """بدنه‌ی stream (تصویر اسکن فشرده) نباید به‌خاطر برخورد تصادفی «/JS» و مانند آن رد شود."""
    import os
    import zlib

    from app.core.document_sanitizer import DocumentRejected, check_pdf

    def build(extra=b""):
        stream = zlib.compress(os.urandom(400_000))
        return (
            b"%PDF-1.7\n1 0 obj\n<< /Type /Catalog " + extra + b">>\nendobj\n2 0 obj\n<< /Length %d >>\nstream\n" % len(stream)
            + stream + b"\nendstream\nendobj\ntrailer\n<<>>\n%%EOF\n"
        )

    for _ in range(15):
        check_pdf(build())
    for bad in (b"/OpenAction << /S /JavaScript /JS (x) >>", b"/Encrypt 3 0 R", b"/J#61vaScript"):
        try:
            check_pdf(build(bad))
        except DocumentRejected:
            continue
        raise AssertionError(bad)
