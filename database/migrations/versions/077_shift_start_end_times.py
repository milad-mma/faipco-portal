"""kara_schema: shift start/end time columns for hourly leave/mission intervals

Revision ID: 077
Revises: 076
Create Date: 2026-09-19

گزارش کاربر: ورود ۰۸:۱۳ با کارت مرخصی در پرتال «۰۸:۱۳ تا ۱۴:۳۷» نمایش داده
می‌شد، در حالی که کاراوب مرخصی را از شروع شیفت (۰۶:۳۰) تا همان ورود حساب
می‌کند (۱:۴۳). برای این محاسبه ساعت شروع/پایان شیفت لازم است؛ برای
سایت‌هایی که جدول شیفت‌ها را نگاشت کرده‌اند نام‌های کاراوب اضافه می‌شود.
"""
import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "077"
down_revision: Union[str, None] = "076"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EXTRA = {
    "shifts.start_time": "Start_Time",
    "shifts.start_time5": "Start_Time5",
    "shifts.end_time": "End_Time",
    "shifts.end_time5": "End_Time5",
}


def _as_dict(value) -> dict:
    if not value:
        return {}
    if isinstance(value, str):
        try:
            return json.loads(value) or {}
        except ValueError:
            return {}
    return dict(value)


def upgrade() -> None:
    bind = op.get_bind()
    for row in bind.execute(sa.text("SELECT id, kara_schema FROM attendance_mappings")).fetchall():
        schema = _as_dict(row.kara_schema)
        if not schema.get("shifts.table"):
            continue
        changed = False
        for key, value in EXTRA.items():
            if not schema.get(key):
                schema[key] = value
                changed = True
        if changed:
            bind.execute(
                sa.text("UPDATE attendance_mappings SET kara_schema = CAST(:v AS JSON) WHERE id = :id"),
                {"v": json.dumps(schema), "id": row.id},
            )


def downgrade() -> None:
    pass
