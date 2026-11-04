"""مجوز «تنظیمات مرخصی/ماموریت» به تفکیک سایت (بدون نیاز به sites.manage)

Revision ID: 148
Revises: 147
"""
from typing import Sequence, Union

from alembic import op

revision: str = "148"
down_revision: Union[str, None] = "147"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO permissions (code, description) VALUES
        ('leave_requests.settings', 'تنظیمات مرخصی/ماموریت سایت: نگاشت کاراوب، نوع‌ها، تأییدکننده‌ی واحدها، مسئول منابع انسانی، وضعیت ماژول و متن اعلان‌ها')
        ON CONFLICT (code) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM role_permissions WHERE permission_id IN (SELECT id FROM permissions WHERE code = 'leave_requests.settings')")
    op.execute("DELETE FROM user_permissions WHERE permission_id IN (SELECT id FROM permissions WHERE code = 'leave_requests.settings')")
    op.execute("DELETE FROM permissions WHERE code = 'leave_requests.settings'")
