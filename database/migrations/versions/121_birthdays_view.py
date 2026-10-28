"""مجوز «مشاهده متولدین سایت‌های دیگر» (birthdays.view)

Revision ID: 121
Revises: 120

کارت «متولدین امروز» دیگر از قاعده‌ی کلی دسترسی سایت (نقش‌های سراسری) پیروی نمی‌کند: هر کس متولدین سایت خودش را
می‌بیند و فقط با birthdays.view متولدین سایت‌های دیگر را — اعطا به تفکیک سایت یا سراسری (= همه‌ی سایت‌ها).
"""
from typing import Sequence, Union

from alembic import op

revision: str = "121"
down_revision: Union[str, None] = "120"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO permissions (code, description)
        VALUES ('birthdays.view', 'مشاهده متولدین امروزِ سایت‌های دیگر در داشبورد (سراسری = همه‌ی سایت‌ها)')
        ON CONFLICT (code) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM role_permissions WHERE permission_id IN (SELECT id FROM permissions WHERE code = 'birthdays.view')"
    )
    op.execute("DELETE FROM permissions WHERE code = 'birthdays.view'")
