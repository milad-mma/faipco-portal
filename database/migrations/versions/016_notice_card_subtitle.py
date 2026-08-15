"""add card_subtitle to notices (زیرعنوان ماه/سال روی خودِ کارت — مستقل از عنوان اطلاعیه)

Revision ID: 016
Revises: 015
Create Date: 2026-08-12

قبلاً زیرعنوان ماه/سال روی خودِ کارت از عنوان اطلاعیه گرفته می‌شد؛ طبق
بازخورد، این باید یک فیلد کاملاً جدا باشد (چون عنوان اطلاعیه برای نمایش در
لیست اطلاعیه‌های دریافتی است، نه لزوماً همان متنی که باید روی خودِ کارت چاپ
شود). این فیلد فقط برای اطلاعیه‌های نوع attendance_card پر می‌شود؛ برای بقیه
انواع همیشه NULL می‌ماند.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "016"
down_revision: Union[str, None] = "015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("notices", sa.Column("card_subtitle", sa.String(length=128), nullable=True))


def downgrade() -> None:
    op.drop_column("notices", "card_subtitle")
