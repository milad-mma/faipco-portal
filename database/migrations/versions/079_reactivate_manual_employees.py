"""reactivate manually created employees wrongly deactivated by sync

Revision ID: 079
Revises: 078
Create Date: 2026-09-20

باگ: Sync هر پرسنلی را که در منبع نبود غیرفعال می‌کرد - از جمله پرسنلی که
دستی در پرتال اضافه شده بودند (و هرگز در منبع نیستند). is_active این پرسنل را
فقط همین باگ False می‌کرد (فعال/غیرفعال‌کردن دستی با is_enabled است)، پس
برگرداندنشان بی‌خطر است.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "079"
down_revision: Union[str, None] = "078"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("UPDATE employees SET is_active = true WHERE is_manually_created = true AND is_active = false")


def downgrade() -> None:
    pass
