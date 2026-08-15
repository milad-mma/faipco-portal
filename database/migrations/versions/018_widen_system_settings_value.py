"""widen system_settings.value to Text (برای پیام‌های سفارشی طولانی‌تر، مثل پیام مسدودسازی IP)

Revision ID: 018
Revises: 017
Create Date: 2026-08-14

قبلاً VARCHAR(500) بود که برای مقادیر کوتاه (مثل فاصله زمانی Sync) کافی بود،
ولی برای متنی که Admin آزادانه می‌نویسد (مثل پیام قابل‌تغییر «VPN را قطع
کنید») باید نامحدودتر باشد.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "018"
down_revision: Union[str, None] = "017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "system_settings",
        "value",
        existing_type=sa.String(length=500),
        type_=sa.Text(),
        existing_nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "system_settings",
        "value",
        existing_type=sa.Text(),
        type_=sa.String(length=500),
        existing_nullable=False,
    )
