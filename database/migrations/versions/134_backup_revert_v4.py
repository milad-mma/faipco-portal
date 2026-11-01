"""بکاپ: حذف باقی‌مانده‌های بکاپ نسخه‌ی ۴ (تصمیم کاربر — همان روش قبلی + فایل‌های آپلودی + رمز ZIP)

- حذف مجوزهای backup.* و اعطاهایشان (نقش و مستقیم)؛ مجوز بکاپ دوباره فقط system.backup (همه‌ی دارندگانش از قبل آن را دارند).
- بازگرداندن توضیح system.backup.
- حذف جدول‌های backup_keys و backup_runs.

Revision ID: 134
Revises: 133
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "134"
down_revision: Union[str, None] = "133"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CODES = ("backup.run_view", "backup.destinations", "backup.download", "backup.key_manage", "backup.restore")


def upgrade() -> None:
    codes = "(" + ",".join(f"'{c}'" for c in CODES) + ")"
    for table in ("role_permissions", "user_permissions"):
        op.execute(f"DELETE FROM {table} WHERE permission_id IN (SELECT id FROM permissions WHERE code IN {codes})")
    op.execute(f"DELETE FROM permissions WHERE code IN {codes}")
    op.get_bind().execute(
        sa.text("UPDATE permissions SET description = :d WHERE code = 'system.backup'"),
        {"d": "پشتیبان‌گیری: دانلود، بازیابی، زمان‌بندی و مقصدهای بکاپ"},
    )
    op.execute("DROP TABLE IF EXISTS backup_runs")
    op.execute("DROP TABLE IF EXISTS backup_keys")


def downgrade() -> None:
    # جدول‌ها و مجوزهای حذف‌شده برنمی‌گردند (Migration 132 دوباره لازم است)
    pass
