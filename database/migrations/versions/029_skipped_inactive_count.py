"""add skipped_inactive_count to sync_logs

Revision ID: 029
Revises: 027
Create Date: 2026-08-23

⚠️ عمداً ۰۲۹ است، نه ۰۲۸ — نسخه اول این تغییر به‌اشتباه با شماره ۰۲۸ روی
سرور ارسال شد، بعد به دلیل تغییر رویکرد (حذف is_cut_column، نگاه کنید
docs/sync-engine.md) دوباره‌نویسی و بازنام‌گذاری شد، ولی چون تحویل فایل‌ها
از طریق Zip است (نه git، که فایل حذف‌شده را واقعاً حذف می‌کند)، فایل قدیمی
هنوز روی سرور می‌ماند — دو فایل «028» همزمان باعث خطای "Multiple head
revisions" می‌شد. با تغییر به ۰۲۹، این تداخل کاملاً دور زده می‌شود.

از دستورات SQL خام با IF EXISTS/IF NOT EXISTS استفاده شده (نه متد استاندارد
op.add_column/op.drop_column) — تا این Migration مستقل از این‌که نسخه
قدیمی «028» (که ستون is_cut_column اضافه می‌کرد) روی این سرور اجرا شده یا
نه، همیشه به‌درستی کار کند.

پرسنلی که در دیتابیس مبدأ (طبق همان یک ستون قابل‌تنظیم is_active_column —
با یا بدون is_active_inverted) غیرفعال باشند، دیگر اصلاً به پرتال Import
نمی‌شوند (نه فقط is_active=False) — اگر قبلاً وارد شده باشند و بعداً
غیرفعال شوند، رکورد و سوابقشان (فیش حقوقی و ...) دست‌نخورده می‌ماند، فقط
is_active=False می‌شود؛ نگاه کنید docs/sync-engine.md.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "029"
down_revision: Union[str, None] = "027"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # اگر نسخه قدیمی و کنارگذاشته‌شده «028» (که ستون is_cut_column را به
    # employee_mappings اضافه می‌کرد) به هر دلیلی روی این سرور اجرا شده
    # باشد، همان ستون غیرضروری را پاک می‌کند — تصمیم نهایی این بود که یک
    # ستون واحد (is_active_column) کافی است، نه دو ستون جدا (نگاه کنید
    # docs/sync-engine.md برای توضیح کامل).
    op.execute("ALTER TABLE employee_mappings DROP COLUMN IF EXISTS is_cut_column")
    # اگر نسخه قدیمی «028» این ستون را از قبل درست اضافه کرده باشد، این خط
    # با IF NOT EXISTS بی‌خطر رد می‌شود؛ در غیر این صورت همین‌جا اضافه می‌شود.
    op.execute(
        "ALTER TABLE sync_logs ADD COLUMN IF NOT EXISTS skipped_inactive_count "
        "INTEGER NOT NULL DEFAULT 0"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE sync_logs DROP COLUMN IF EXISTS skipped_inactive_count")
