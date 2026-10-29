"""مجوز پیام تبریک تولد زیر شاخه‌ی birthdays: hr.birthday_messages → birthdays.messages

Revision ID: 122
Revises: 121

درخت مجوزها بر اساس پیشوند کد گروه‌بندی می‌شود؛ با تغییر کد، «پیام‌های تبریک تولد» کنار «birthdays.view» می‌نشیند.
همان ردیف مجوز تغییر نام می‌کند، پس اعطاهای فعلی (نقش‌ها و مجوزهای مستقیم) دست نمی‌خورند.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "122"
down_revision: Union[str, None] = "121"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE permissions
        SET code = 'birthdays.messages',
            description = 'مدیریت پیام‌های تبریک تولد (متن‌ها، ساعت ارسال و خروجی متولدین)'
        WHERE code = 'hr.birthday_messages'
          AND NOT EXISTS (SELECT 1 FROM permissions WHERE code = 'birthdays.messages')
        """
    )


def downgrade() -> None:
    op.execute(
        """
        UPDATE permissions SET code = 'hr.birthday_messages'
        WHERE code = 'birthdays.messages'
          AND NOT EXISTS (SELECT 1 FROM permissions WHERE code = 'hr.birthday_messages')
        """
    )
