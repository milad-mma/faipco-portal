"""kara_schema: DailyWork card columns + shift AddedDay (night/rotating shifts)

Revision ID: 078
Revises: 077
Create Date: 2026-09-19

برای شیفت شب و گردشی: کاراوب ترددهای بعد از نیمه‌شب را به همان روزِ شیفت
نسبت می‌دهد (کارکرد روزانه، Card1..Card24، ساعت +۲۴۰۰) و پایان شیفت شب روز
بعد است (Shifts.AddedDay). گزارش تردد ترتیب ورود/خروج و بازه مرخصی/ماموریت
ساعتی را از همین‌ها می‌خواند.
"""
import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "078"
down_revision: Union[str, None] = "077"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

EXTRA = {
    "shifts": {"shifts.added_day": "AddedDay", "shifts.added_day5": "AddedDay5"},
    "daily_work": {"daily_work.card_prefix": "Card"},
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
        changed = False
        for group, values in EXTRA.items():
            if not schema.get(f"{group}.table"):
                continue
            for key, value in values.items():
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
