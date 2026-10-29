"""پرسنل آنلاین: صفحه‌ای که شخص الان در پرتال باز کرده

Revision ID: 129
Revises: 128

presence_sessions.current_page (مسیر صفحه بدون پارامترها، مثل /leave-requests) و page_seen_at (از کی در این صفحه است)؛
با هر Heartbeat و هر جابه‌جایی بین صفحه‌ها از WebSocket حضور به‌روز می‌شود.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "129"
down_revision: Union[str, None] = "128"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("presence_sessions", sa.Column("current_page", sa.String(200), nullable=True))
    op.add_column("presence_sessions", sa.Column("page_seen_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("presence_sessions", "page_seen_at")
    op.drop_column("presence_sessions", "current_page")
