"""notices.site_report permission — replaces hardcoded site_manager check

Revision ID: 035
Revises: 034
Create Date: 2026-08-27

قابلیت «گزارش اطلاعیه‌های سایت من» تا امروز مستقیماً به نام نقش
«site_manager» Hard-code شده بود (نه یک Permission Code)؛ یعنی هیچ نقش
دیگری — هرچقدر هم که از پنل مجوز بگیرد — نمی‌توانست این گزارش را ببیند.
این Migration یک مجوز واقعی (notices.site_report) می‌سازد و آن را به
همان نقش site_manager هم وصل می‌کند — تا رفتار فعلی برای کسانی که همین
الان این نقش را دارند، دقیقاً همان‌طور که بود باقی بماند؛ از این به بعد
Admin می‌تواند همین مجوز را به هر نقش دیگری هم (از پنل «مدیریت
نقش/مجوز») بدهد.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "035"
down_revision: Union[str, None] = "034"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO permissions (code, description)
        VALUES ('notices.site_report', 'گزارش اطلاعیه‌های رسیده به سایت(های) تحت مدیریت (فقط‌خواندنی)')
        ON CONFLICT (code) DO NOTHING
        """
    )
    # همان دسترسی که site_manager تا امروز به‌صورت Hard-code داشت، حالا
    # واقعاً از طریق همین مجوز به آن وصل می‌شود — بدون هیچ تغییری در
    # تجربه کسانی که همین الان این نقش را دارند.
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r, permissions p
        WHERE r.name = 'site_manager' AND p.code = 'notices.site_report'
        ON CONFLICT (role_id, permission_id) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute(
        """
        DELETE FROM role_permissions
        WHERE permission_id IN (SELECT id FROM permissions WHERE code = 'notices.site_report')
        """
    )
    op.execute("DELETE FROM permissions WHERE code = 'notices.site_report'")
