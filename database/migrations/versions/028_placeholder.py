"""placeholder for a since-removed revision 028

Revision ID: 028
Revises: 027
Create Date: 2026-08-23

⚠️ این فایل عمداً یک Placeholder خالی است، نه یک Migration واقعی جدید.

داستان کامل: نسخه اول این تغییر (اضافه‌کردن is_cut_column) با شماره ۰۲۸
روی بعضی سرورها Deploy و با موفقیت اجرا شد — یعنی جدول alembic_version
آن‌ها همین الان مقدار "028" را دارد. بعداً به دلیل تغییر رویکرد (حذف
is_cut_column، نگاه کنید docs/sync-engine.md) آن فایل با محتوای متفاوت
بازنویسی و در نهایت به نسخه ۰۲۹ منتقل شد. اگر فایل قدیمی «028» به‌طور
کامل حذف می‌شد، Alembic روی هر سروری که از قبل به "028" رسیده بود با خطای
«Can't locate revision identified by '028'» متوقف می‌شد — چون دیگر هیچ
فایلی با این Revision ID برای پیداکردن جایگاهش در زنجیره تاریخچه وجود
نداشت.

این فایل دقیقاً همان جای خالی را پر می‌کند — بدون هیچ تغییر واقعی در
دیتابیس (upgrade/downgrade هر دو خالی‌اند) — تا زنجیره ۰۲۷ → ۰۲۸ → ۰۲۹
دوباره پیوسته و قابل‌فهم برای Alembic شود، چه روی سروری که قبلاً به "028"
رسیده بود (و اینجا فقط یک ایستگاه بی‌اثر رد می‌کند) چه روی نصب کاملاً تازه
(که این و بعدی را پشت‌سرهم و بدون وقفه اجرا می‌کند).
"""
from typing import Sequence, Union

revision: str = "028"
down_revision: Union[str, None] = "027"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
