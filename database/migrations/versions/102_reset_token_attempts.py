"""سخت‌سازی توکن بازنشانی رمز: ستون attempts و حذف یکتایی token

Revision ID: 102
Revises: 101
Create Date: 2026-10-05

- attempts: شمارنده‌ی کدهای اشتباه برای هر توکن؛ پس از چند تلاش ناموفق توکن باطل می‌شود
  (جلوگیری از حدس کد ۶ رقمی پیامکی روی حساب یک کاربر مشخص).
- یکتایی ستون token حذف می‌شود: از این نسخه فقط هش SHA-256 کد/توکن ذخیره می‌شود و جست‌وجو همیشه
  با (user_id, token) است؛ کد ۶ رقمی دو کاربر می‌تواند یکسان باشد و یکتایی باعث خطای درج می‌شد.
- توکن‌های فعلی (متن خام) دیگر با هش تطابق ندارند؛ چون عمرشان حداکثر ۱۰ دقیقه است، حذف می‌شوند.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "102"
down_revision: Union[str, None] = "101"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "password_reset_tokens",
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
    )
    # نام پیش‌فرض محدودیت یکتا در PostgreSQL برای unique=True روی ستون: <table>_<column>_key
    op.execute("ALTER TABLE password_reset_tokens DROP CONSTRAINT IF EXISTS password_reset_tokens_token_key")
    # ایندکس غیر‌یکتا برای جست‌وجو می‌ماند (در 045 جدا ساخته شده)؛ اگر نبود، ساخته می‌شود
    op.execute("CREATE INDEX IF NOT EXISTS ix_password_reset_tokens_token ON password_reset_tokens (token)")
    # توکن‌های خام قبلی با منطق هش جدید قابل تطبیق نیستند؛ عمر کوتاه دارند و پاک می‌شوند
    op.execute("DELETE FROM password_reset_tokens WHERE used_at IS NULL")


def downgrade() -> None:
    op.execute("DELETE FROM password_reset_tokens")  # هش‌ها با کد قبلی (متن خام) قابل استفاده نیستند
    op.create_unique_constraint("password_reset_tokens_token_key", "password_reset_tokens", ["token"])
    op.drop_column("password_reset_tokens", "attempts")
