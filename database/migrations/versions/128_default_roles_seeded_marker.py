"""نقش پیش‌فرضی که یک بار ساخته شده، دیگر هرگز دوباره ساخته نشود (حتی اگر ادمین نامش را عوض یا حذفش کرده باشد)

Revision ID: 128
Revises: 127

Migration 127 نقش تغییرنام‌داده را از روی نام اولیه یا توضیح پیش‌فرض پیدا می‌کرد؛ اگر ادمین توضیح را هم عوض کرده (یا
نسخه‌های تکراری را خودش حذف کرده) بود، پیدا نمی‌شد و seed دوباره همان نقش را با نام اولیه می‌ساخت.

از این به بعد seed فهرست «نقش‌های پیش‌فرضی که قبلاً ساخته شده‌اند» را در system_settings
(کلید seed.default_roles_done) نگه می‌دارد و نقشِ داخل فهرست را هرگز دوباره نمی‌سازد. برای نصب‌های موجود (که
superadmin دارند) همه‌ی نقش‌های پیش‌فرض «ساخته‌شده» علامت می‌خورند؛ نصب تازه همچنان آن‌ها را یک بار می‌سازد.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "128"
down_revision: Union[str, None] = "127"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

KEYS = "superadmin,site_manager,middle_manager,acc_manager,hr-manager"


def upgrade() -> None:
    op.execute(
        f"""
        INSERT INTO system_settings (key, value)
        SELECT 'seed.default_roles_done', '{KEYS}'
        WHERE EXISTS (SELECT 1 FROM roles WHERE name = 'superadmin' OR system_key = 'superadmin')
        ON CONFLICT (key) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM system_settings WHERE key = 'seed.default_roles_done'")
