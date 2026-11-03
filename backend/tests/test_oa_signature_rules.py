"""امضای شخصی: برش حاشیه، حذف پس‌زمینه، PNG بدون metadata، رد SVG و تصویر خالی/بزرگ."""

import io

from PIL import Image, ImageDraw

from app.core import oa_signature_rules as R


def _png(size, bg, draw=True, mode="RGBA", fmt="PNG", exif=False):
    im = Image.new(mode, size, bg)
    if draw:
        d = ImageDraw.Draw(im)
        d.line([(100, 120), (300, 160), (420, 110)], fill=(10, 20, 120, 255) if mode == "RGBA" else (10, 20, 120), width=8)
    buf = io.BytesIO()
    kw = {}
    if exif:
        e = Image.Exif()
        e[0x010E] = "secret description"
        kw["exif"] = e
    im.save(buf, fmt, **kw)
    return buf.getvalue()


def _raises(fn, *a, **k):
    try:
        fn(*a, **k)
    except R.SignatureRulesError as e:
        return str(e)
    raise AssertionError("expected SignatureRulesError")


def test_drawn_transparent_is_cropped():
    out = R.process_signature(_png((800, 400), (0, 0, 0, 0)), remove_background=False)
    im = Image.open(io.BytesIO(out))
    assert im.format == "PNG" and im.mode == "RGBA"
    assert im.width < 400 and im.height < 100  # حاشیه‌ی خالی بریده شد
    assert im.getpixel((0, 0))[3] == 0


def test_white_background_removed_and_metadata_stripped():
    raw = _png((800, 400), (255, 255, 255), mode="RGB", fmt="JPEG", exif=True)
    out = R.process_signature(raw, remove_background=True)
    im = Image.open(io.BytesIO(out))
    assert im.getpixel((0, 0))[3] == 0  # گوشه شفاف شد
    assert not im.info.get("exif") and b"secret" not in out


def test_rejections():
    assert "امضایی" in _raises(R.process_signature, _png((400, 200), (0, 0, 0, 0), draw=False), remove_background=False)
    assert "PNG" in _raises(R.process_signature, b"<svg xmlns='http://www.w3.org/2000/svg'></svg>", remove_background=False)
    assert "معتبر" in _raises(R.process_signature, b"not an image", remove_background=False)
    assert "۲ مگابایت" in _raises(R.process_signature, b"x" * (R.MAX_UPLOAD_BYTES + 1), remove_background=False)
    big = _png((4100, 100), (255, 255, 255), mode="RGB")
    assert "ابعاد" in _raises(R.process_signature, big, remove_background=True)
