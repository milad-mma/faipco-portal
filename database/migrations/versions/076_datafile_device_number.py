"""kara_schema: datafile.device_number for forgotten-punch insert

Revision ID: 076
Revises: 075
Create Date: 2026-09-19

خطای واقعی هنگام تأیید نهایی تردد فراموش‌شده: ستون DeviceNumber جدول تردد
کاراوب یک پیش‌فرض دیتابیسی (DF_DataFile_Clock_No) دارد که شماره دستگاه
نامعتبری است و با FK_DataFile_Devices خطا می‌دهد؛ کاراوب خودش این ستون را
صریحاً NULL می‌نویسد. نام این ستون برای سایت‌هایی که ستون‌های تکمیلی جدول
تردد را نگاشت کرده‌اند اضافه می‌شود.
"""
import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "076"
down_revision: Union[str, None] = "075"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


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
        if schema.get("datafile.status") and not schema.get("datafile.device_number"):
            schema["datafile.device_number"] = "DeviceNumber"
            bind.execute(
                sa.text("UPDATE attendance_mappings SET kara_schema = CAST(:v AS JSON) WHERE id = :id"),
                {"v": json.dumps(schema), "id": row.id},
            )


def downgrade() -> None:
    pass
