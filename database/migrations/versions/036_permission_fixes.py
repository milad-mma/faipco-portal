"""remove notices.target.role + correct outdated permission descriptions

Revision ID: 036
Revises: 035
Create Date: 2026-08-28

دو کار مستقل:

۱) حذف کامل مجوز notices.target.role — طبق درخواست صریح، این قابلیت
   (هدف‌گیری اطلاعیه بر اساس نقش) اصلاً هیچ رابط کاربری‌ای نداشت و حذف
   شد. خودِ ردیف Permission (و هر RolePermission که بهش وصل بود) حذف
   می‌شود؛ NoticeTargetType.role در سطح Enum دیتابیس دست‌نخورده می‌ماند
   (برای ایمنی داده‌های تاریخی احتمالی)، فقط دیگر قابل استفاده نیست.

۲) تصحیح توضیح چند مجوز که یا نادرست بودند (چند مورد «فقط superadmin»
   می‌گفتند، در حالی که بعد از اصلاحات اخیر سیستم مجوز، واقعاً قابل
   تخصیص به هر نقشی‌اند) یا اصلاً کاری نمی‌کردند (sites.view که تا امروز
   کاملاً بلااستفاده بود) — همه این توضیحات بر اساس یک بررسی کامل و
   واقعی کد اصلاح شدند، نه فقط حدس.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "036"
down_revision: Union[str, None] = "035"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (کد, توضیح جدید و دقیق)
_DESCRIPTION_FIXES = [
    (
        "attendance.view_logs",
        "مشاهده گزارش «پرسنل آنلاین» (Session‌های زنده GPS) — محدود به "
        "سایت‌هایی که این نقش برایشان تعریف شده (نه لزوماً کل سازمان)؛ "
        "به هر نقشی قابل تخصیص است.",
    ),
    (
        "notices.target.all",
        "ارسال اطلاعیه به کل سازمان (Broadcast) — به هر نقشی قابل تخصیص "
        "است؛ معمولاً فقط برای نقش‌های سطح بالا (مثل مدیرعامل) منطقی است.",
    ),
    (
        "notices.view",
        "مشاهده لیست کامل اطلاعیه‌های *همه* سازمان (نه فقط اطلاعیه‌های "
        "دریافتی خودِ کاربر) — یک قابلیت سطح Backend، فعلاً هیچ صفحه‌ای "
        "در پنل کاربری به آن وصل نیست. ⚠️ همه پرسنل، صرف‌نظر از این "
        "مجوز، اطلاعیه‌های خودشان را از صفحه «اطلاعیه‌ها» می‌بینند — آن "
        "مسیر کاملاً جدا و مستقل از این مجوز است؛ پس این مجوز را نباید "
        "با «همه به‌طور پیش‌فرض این را دارند» اشتباه گرفت.",
    ),
    (
        "sites.view",
        "مشاهده فقط‌خواندنی صفحه «سایت‌ها» — بدون افزودن/ویرایش/حذف/"
        "فعال‌سازی سایت یا تغییر اتصال دیتابیس (آن‌ها فقط با sites.manage).",
    ),
    (
        "system.backup",
        "دانلود بکاپ کامل سیستم — به هر نقشی قابل تخصیص است.",
    ),
    (
        "system.cache_bust",
        "پاک‌کردن کش اپ برای همه کاربران (نصب اجباری نسخه تازه) — به هر "
        "نقشی قابل تخصیص است.",
    ),
    (
        "system.ip_allowlist",
        "مدیریت رنج‌های IP مجاز برای ورود — به هر نقشی قابل تخصیص است.",
    ),
]


def upgrade() -> None:
    from sqlalchemy import text

    op.execute(
        "DELETE FROM role_permissions WHERE permission_id IN "
        "(SELECT id FROM permissions WHERE code = 'notices.target.role')"
    )
    op.execute("DELETE FROM permissions WHERE code = 'notices.target.role'")

    # به‌روزرسانی امن با پارامتر (نه رشته‌سازی مستقیم متن)
    bind = op.get_bind()
    for code, description in _DESCRIPTION_FIXES:
        bind.execute(
            text("UPDATE permissions SET description = :description WHERE code = :code"),
            {"description": description, "code": code},
        )


def downgrade() -> None:
    # بازگرداندن دقیق توضیحات قبلی ضروری نیست (فقط متن است، نه ساختار
    # داده) — در صورت Downgrade، توضیحات جدید (دقیق‌تر) باقی می‌مانند.
    op.execute(
        """
        INSERT INTO permissions (code, description)
        VALUES ('notices.target.role', 'ارسال اطلاعیه به یک نقش خاص')
        ON CONFLICT (code) DO NOTHING
        """
    )
