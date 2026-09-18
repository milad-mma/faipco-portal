"""
واترمارک تصویر پرسنل — نام و کد پرسنلیِ **بیننده** روی عکس حک می‌شود.

⚠️ چرا این کار: جلوگیری کامل از ذخیره تصویر در مرورگر ممکن نیست (هر
چیزی که مرورگر نمایش می‌دهد قابل‌اسکرین‌شات و قابل‌استخراج از تب Network
است). به‌جای وعده امنیتی غیرواقعی، اینجا **بازدارندگی** ساخته می‌شود:
هر عکس نشت‌یافته مستقیماً به کسی که آن را دیده برمی‌گردد.

⚠️ واترمارک عمداً کم‌رنگ و در کل تصویر تکرار می‌شود - نه یک برچسب گوشه
که با برش ساده حذف شود.
"""
from __future__ import annotations

import io
import logging

logger = logging.getLogger(__name__)


def add_viewer_watermark(image_bytes: bytes, viewer_label: str) -> tuple[bytes, str]:
    """
    واترمارک را روی تصویر حک می‌کند و (بایت‌ها، media_type) برمی‌گرداند.

    ⚠️ اگر هر خطایی رخ دهد (فرمت ناشناخته، نبود Pillow، تصویر خراب)،
    تصویر **اصلی و بدون واترمارک** برگردانده می‌شود - چون نمایش‌نشدن
    آواتار بدتر از نمایش بدون واترمارک است و نباید کل صفحه را بشکند.
    """
    try:
        from PIL import Image, ImageDraw

        source = Image.open(io.BytesIO(image_bytes))
        # تصاویر GIF/P باید به RGBA تبدیل شوند تا لایه شفاف قابل‌ترکیب باشد
        base = source.convert("RGBA")
        width, height = base.size

        overlay = Image.new("RGBA", base.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(overlay)

        # ⚠️ فونت پیش‌فرض Pillow استفاده می‌شود (نه فونت فارسی): متن
        # واترمارک فقط کد پرسنلی و ارقام است تا وابسته به فونت فارسی و
        # shaping راست‌به‌چپ نباشد - که روی سرور ممکن است موجود نباشد.
        text = viewer_label
        step_x = max(60, width // 2)
        step_y = max(30, height // 3)

        for y in range(0, height + step_y, step_y):
            for x in range(0, width + step_x, step_x):
                draw.text((x, y), text, fill=(255, 255, 255, 90))
                draw.text((x + 1, y + 1), text, fill=(0, 0, 0, 70))

        combined = Image.alpha_composite(base, overlay).convert("RGB")
        out = io.BytesIO()
        combined.save(out, format="PNG")
        return out.getvalue(), "image/png"
    except Exception:
        logger.exception("افزودن واترمارک به تصویر پرسنل با خطا مواجه شد - تصویر اصلی برگردانده شد")
        return image_bytes, "image/gif"


def viewer_label_for(user, employee=None) -> str:
    """
    برچسب بیننده - کد پرسنلی اگر موجود باشد، وگرنه شناسه کاربر.

    ⚠️ عمداً فقط شناسه عددی/کد استفاده می‌شود، نه نام فارسی: هم برای
    اجتناب از وابستگی به فونت فارسی، هم چون کد پرسنلی برای پیگیری
    دقیق‌تر و بدون ابهام است.
    """
    if employee is not None and getattr(employee, "personnel_code", None):
        return str(employee.personnel_code)
    return f"U{user.id}"
