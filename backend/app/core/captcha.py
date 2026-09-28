"""
ساخت تصویر کپچای داخلی (بدون وابستگی به سرویس بیرونی؛ در شبکه‌ی داخلی و قطعی اینترنت هم کار می‌کند).

- متن: ارقام تصادفی (CAPTCHA_LENGTH رقم)، با ارقام فارسی و فونت Tahoma همراه پروژه رسم می‌شود. کاربر می‌تواند
  با کیبورد فارسی یا انگلیسی پاسخ دهد (پاسخ یکسان‌سازی می‌شود).
- هر رقم با اندازه، چرخش و جابه‌جایی تصادفی؛ خطوط منحنی و نقاط نویز روی تصویر.
- خروجی PNG. پاسخ هرگز به کلاینت فرستاده نمی‌شود؛ فقط هش HMAC آن در دیتابیس می‌ماند.
"""
from __future__ import annotations

import io
import math
import secrets
from functools import lru_cache
from pathlib import Path

CAPTCHA_LENGTH = 5
WIDTH, HEIGHT = 220, 72
_FA_DIGITS = "۰۱۲۳۴۵۶۷۸۹"
_FONT_PATH = Path(__file__).resolve().parent.parent / "assets" / "fonts" / "Tahoma.ttf"
_rng = secrets.SystemRandom()


_ALLOWED_DIGITS = "23456789"  # «۰» فارسی یک نقطه است و «۱» با خط نویز اشتباه می‌شود؛ هر دو کنار گذاشته شده‌اند


def random_answer(length: int = CAPTCHA_LENGTH) -> str:
    """رشته‌ی ارقام لاتین تصادفی (رمزنگارانه امن)."""
    return "".join(secrets.choice(_ALLOWED_DIGITS) for _ in range(length))


@lru_cache(maxsize=8)
def _font(size: int):
    from PIL import ImageFont

    try:
        return ImageFont.truetype(str(_FONT_PATH), size)
    except OSError:  # نبود فونت: فونت پیش‌فرض Pillow (ارقام لاتین)
        return ImageFont.load_default(size=size)


def render_captcha_png(answer: str) -> bytes:
    """ورودی: ارقام لاتین. خروجی: بایت‌های PNG تصویر کپچا."""
    from PIL import Image, ImageDraw, ImageFilter

    img = Image.new("RGB", (WIDTH, HEIGHT), (246, 248, 251))
    draw = ImageDraw.Draw(img)

    # نقاط نویز پس‌زمینه
    for _ in range(260):
        x, y = _rng.randrange(WIDTH), _rng.randrange(HEIGHT)
        shade = _rng.randrange(150, 220)
        draw.point((x, y), fill=(shade, shade, shade + 20 if shade < 235 else 255))

    # هر رقم روی یک لایه‌ی جدا رسم و با چرخش تصادفی روی تصویر گذاشته می‌شود
    use_persian = _FONT_PATH.exists()
    slot = (WIDTH - 20) / len(answer)
    for i, ch in enumerate(answer):
        glyph = _FA_DIGITS[int(ch)] if use_persian else ch
        size = _rng.randrange(44, 54)
        layer = Image.new("RGBA", (64, 76), (0, 0, 0, 0))
        color = (_rng.randrange(20, 90), _rng.randrange(30, 90), _rng.randrange(90, 160), 255)
        ImageDraw.Draw(layer).text((10, 0), glyph, font=_font(size), fill=color)
        layer = layer.rotate(_rng.uniform(-28, 28), resample=Image.BICUBIC, expand=False)
        x = int(10 + i * slot + _rng.uniform(-4, 4))
        y = int(_rng.uniform(-10, 0))
        img.paste(layer, (x, y), layer)

    # خطوط منحنی روی ارقام
    for _ in range(3):
        amp, freq, phase = _rng.uniform(4, 12), _rng.uniform(0.02, 0.06), _rng.uniform(0, math.pi * 2)
        base = _rng.uniform(18, HEIGHT - 18)
        color = (_rng.randrange(60, 140), _rng.randrange(60, 140), _rng.randrange(100, 180))
        points = [(x, base + amp * math.sin(freq * x + phase)) for x in range(0, WIDTH, 4)]
        draw.line(points, fill=color, width=1)

    img = img.filter(ImageFilter.SMOOTH)
    out = io.BytesIO()
    img.save(out, format="PNG", optimize=True)
    return out.getvalue()
