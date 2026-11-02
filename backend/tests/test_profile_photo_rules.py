"""تست آماده‌سازی عکس پرسنلی مثل کاراوب: نگه داشتن فایل کوچک، کوچک‌سازی فایل بزرگ، عکس کوچک GIF ۸۸×۸۸ با پالت GDI+."""

import io

from PIL import Image

from app.core import profile_photo_rules as R


def _img(size, fmt, color=(200, 120, 60), mode="RGB"):
    im = Image.new(mode, size, color)
    # کمی جزئیات تا فشرده‌سازی واقعی باشد
    for x in range(0, size[0], 7):
        for y in range(0, size[1], 11):
            im.putpixel((x, y), (x % 256, y % 256, (x * y) % 256) if mode == "RGB" else (x % 256, y % 256, 10, 128))
    buf = io.BytesIO()
    im.save(buf, fmt)
    return buf.getvalue()


def _raises(fn, *a):
    try:
        fn(*a)
    except R.PhotoRulesError as e:
        return str(e)
    raise AssertionError("expected PhotoRulesError")


def test_palette_matches_kara_order():
    pal = R.halftone_palette()
    assert len(pal) == 768
    # ابتدای پالت کاراوب: 000000 000033 000066 000099 0000CC 0000FF 002B00
    assert bytes(pal[:21]).hex() == "000000000033000066000099" "0000cc0000ff002b00"
    assert bytes(pal[252 * 3:]).hex() == "00" * 12


def test_small_jpeg_kept_byte_for_byte():
    raw = _img((300, 300), "JPEG")
    assert len(raw) < R.KARA_MAX_BYTES
    main, thumb = R.prepare_upload(raw)
    assert main == raw


def test_large_image_shrunk_under_kara_limit():
    raw = _img((3000, 2000), "PNG")
    main, _ = R.prepare_upload(raw)
    assert len(main) < R.KARA_MAX_BYTES
    im = Image.open(io.BytesIO(main))
    assert im.format == "JPEG" and max(im.size) <= R.MAX_SIDE_PX


def test_thumbnail_is_kara_style_gif():
    _, thumb = R.prepare_upload(_img((400, 600), "PNG"))  # غیرمربع → کشیده
    assert thumb[:6] == b"GIF89a" and thumb[6:10] == bytes.fromhex("58005800") and thumb[10] == 0xF7
    g = Image.open(io.BytesIO(thumb))
    assert g.size == (88, 88) and g.info.get("transparency") == 252
    assert g.getpalette()[:768] == R.halftone_palette()
    assert 252 not in set(g.getdata())  # خانه‌ی شفاف استفاده نمی‌شود


def test_transparent_png_and_webp_accepted():
    main, _ = R.prepare_upload(_img((200, 200), "PNG", (0, 0, 0, 0), mode="RGBA"))
    assert main  # PNG کوچک همان‌طور نگه داشته می‌شود
    main, _ = R.prepare_upload(_img((200, 200), "WEBP"))
    assert Image.open(io.BytesIO(main)).format == "JPEG"


def test_invalid_inputs():
    assert "انتخاب نشده" in _raises(R.prepare_upload, b"")
    assert "معتبر" in _raises(R.prepare_upload, b"not an image at all")
    assert "کوچک" in _raises(R.prepare_upload, _img((40, 40), "PNG"))


def test_media_type():
    assert R.image_media_type(b"\xff\xd8\xff\xe0x") == "image/jpeg"
    assert R.image_media_type(b"\x89PNG\r\n\x1a\nxx") == "image/png"
    assert R.image_media_type(b"GIF89a") == "image/gif"
