"""بیمه تکمیلی: فعال/غیرفعال به‌ازای سایت (insurance_site_settings)

Revision ID: 100
Revises: 099
Create Date: 2026-10-04

قبلاً کلید enabled در system_settings.insurance_settings برای کل سازمان بود. حالا هر سایت یک ردیف اختیاری دارد؛
نبودِ ردیف = فعال. اگر کلید سراسری قبلی خاموش بود، برای همه‌ی سایت‌های موجود ردیف غیرفعال ساخته می‌شود
تا رفتار فعلی حفظ شود. کلید سراسری دیگر خوانده نمی‌شود.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "100"
down_revision: Union[str, None] = "099"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "insurance_site_settings",
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("is_disabled", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    # حفظ رفتار قبلی: اگر ماژول سراسری خاموش بود، همه‌ی سایت‌ها غیرفعال می‌شوند
    op.execute(
        """
        INSERT INTO insurance_site_settings (site_id, is_disabled)
        SELECT s.id, true FROM sites s
        WHERE EXISTS (
            SELECT 1 FROM system_settings ss
            WHERE ss.key = 'insurance_settings'
              AND ss.value::jsonb ->> 'enabled' IN ('false', '0')
        )
        """
    )


def downgrade() -> None:
    op.drop_table("insurance_site_settings")
