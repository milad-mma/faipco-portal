"""family_profiles: سابقه‌ی بیمه‌ی پیش از استخدام (اعلام پرسنل / منابع انسانی)

Revision ID: 098
Revises: 097
Create Date: 2026-10-03

سابقه‌ی بیمه دیگر برای همه دستی وارد نمی‌شود: روزهای پس از استخدام از تاریخ استخدام (کاراوب) خودکار حساب
می‌شود و با «سابقه‌ی پیش از استخدام» جمع می‌شود.
- prior_insurance_days: اعلام خود پرسنل در فرم (همراه پرینت سوابق بیمه، با تأیید منابع انسانی)
- hr_prior_insurance_days: ثبت منابع انسانی (دستی یا ورود گروهی از Excel)؛ بر اعلام پرسنل مقدم است
ستون insurance_days (موجود) از این پس «کل سابقه» است که در صورت ثبت، جایگزین محاسبه می‌شود.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "098"
down_revision: Union[str, None] = "097"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("family_profiles", sa.Column("prior_insurance_days", sa.Integer(), nullable=True))
    op.add_column("family_profiles", sa.Column("hr_prior_insurance_days", sa.Integer(), nullable=True))


def downgrade() -> None:
    op.drop_column("family_profiles", "hr_prior_insurance_days")
    op.drop_column("family_profiles", "prior_insurance_days")
