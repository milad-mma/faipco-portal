"""
واترمارک تصویر پرسنل: شناسه‌ی **بیننده** (کد پرسنلی یا شناسه کاربر) روی عکس حک می‌شود.

جلوگیری کامل از ذخیره تصویر در مرورگر ممکن نیست (هر چیزی که نمایش داده شود
قابل اسکرین‌شات است)؛ این ماژول بازدارندگی ایجاد می‌کند: هر عکس نشت‌یافته
به کسی که آن را دیده قابل ردیابی است.
واترمارک کم‌رنگ است و در کل تصویر تکرار می‌شود تا با برش ساده حذف نشود.
شامل: add_viewer_watermark (حک واترمارک) و viewer_label_for (ساخت برچسب بیننده).
"""
from __future__ import annotations

import io
import logging

logger = logging.getLogger(__name__)


def add_viewer_watermark(image_bytes: bytes, viewer_label: str) -> tuple[bytes, str]:
    """
    ورودی: بایت‌های تصویر و برچسب بیننده. برچسب را به‌صورت کاشی‌شده روی تصویر حک می‌کند.
    خروجی: (بایت‌های PNG، "image/png").
    در صورت هر خطا (فرمت ناشناخته، نبود Pillow، تصویر خراب) تصویر اصلی بدون واترمارک برمی‌گردد.
    """
    try:
        from PIL import Image, ImageDraw

        source = Image.open(io.BytesIO(image_bytes))
        # تصاویر GIF/P باید به RGBA تبدیل شوند تا لایه شفاف قابل‌ترکیب باشد
        base = source.convert("RGBA")
        width, height = base.size

        # لایه‌ی شفاف جداگانه برای متن واترمارک
        overlay = Image.new("RGBA", base.size, (255, 255, 255, 0))
        draw = ImageDraw.Draw(overlay)

        # فونت پیش‌فرض Pillow استفاده می‌شود: متن فقط کد پرسنلی و ارقام است
        # و به فونت فارسی یا shaping راست‌به‌چپ روی سرور نیاز ندارد.
        text = viewer_label
        step_x = max(60, width // 2)  # فاصله افقی تکرار: دو ستون در عرض تصویر
        step_y = max(30, height // 3)  # فاصله عمودی تکرار: سه ردیف در ارتفاع تصویر

        # تکرار متن در کل تصویر (شبکه‌ای)
        for y in range(0, height + step_y, step_y):
            for x in range(0, width + step_x, step_x):
                draw.text((x, y), text, fill=(255, 255, 255, 90))  # متن سفید نیمه‌شفاف
                draw.text((x + 1, y + 1), text, fill=(0, 0, 0, 70))  # سایه‌ی تیره یک پیکسل پایین‌تر برای خوانایی روی زمینه روشن

        # ترکیب لایه با تصویر و خروجی PNG
        combined = Image.alpha_composite(base, overlay).convert("RGB")
        out = io.BytesIO()
        combined.save(out, format="PNG")
        return out.getvalue(), "image/png"
    except Exception:
        logger.exception("افزودن واترمارک به تصویر پرسنل با خطا مواجه شد - تصویر اصلی برگردانده شد")
        return image_bytes, "image/gif"


def viewer_label_for(user, employee=None) -> str:
    """
    ورودی: کاربر بیننده و (اختیاری) رکورد پرسنل او.
    خروجی: کد پرسنلی اگر موجود باشد، وگرنه "U" + شناسه کاربر.
    فقط شناسه عددی استفاده می‌شود (نه نام فارسی) تا به فونت فارسی وابسته نباشد و ردیابی دقیق باشد.
    """
    if employee is not None and getattr(employee, "personnel_code", None):
        return str(employee.personnel_code)
    return f"U{user.id}"
