"""split kara_schema between attendance & leave mappings; drop kara_writeback_enabled

Revision ID: 074
Revises: 073
Create Date: 2026-09-19

طبق درخواست صریح کاربر:
  - تیک «ثبت در کارکرد کاراوب» حذف شد: هر قابلیت فقط وقتی فعال است که
    جدول‌هایش نگاشت شده باشند (مثل بقیه نگاشت‌ها).
  - جدول تردد دوبار نگاشت نمی‌شود: ستون‌های تکمیلی تردد، لاگ تردد، کارکرد
    روزانه، شیفت‌ها و تقویم گروهی به نگاشت تردد (attendance_mappings) منتقل
    شدند و جدول/کد پرسنلی/تاریخ/ساعت تردد از همان نگاشت خوانده می‌شود.

داده: سایت‌هایی که قبلاً این قابلیت برایشان روشن بود، نام‌های کاراوب
(پیش‌فرض + هر تغییری که ادمین داده بود) را به‌صورت کامل ذخیره‌شده می‌گیرند
تا رفتار فعلی‌شان عوض نشود؛ سایت‌هایی که خاموش بود، خالی (= غیرفعال).
"""
import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

from app.services.kara_schema import ATTENDANCE_SCHEMA_DEFAULTS, LEAVE_SCHEMA_DEFAULTS

revision: str = "074"
down_revision: Union[str, None] = "073"
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
    op.add_column(
        "attendance_mappings",
        sa.Column("kara_schema", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
    )

    bind = op.get_bind()
    leave_rows = bind.execute(
        sa.text("SELECT id, site_id, kara_writeback_enabled, kara_schema FROM leave_request_mappings")
    ).fetchall()
    for row in leave_rows:
        overrides = _as_dict(row.kara_schema)
        if row.kara_writeback_enabled:
            leave_schema = {k: overrides.get(k) or v for k, v in LEAVE_SCHEMA_DEFAULTS.items()}
            attendance_schema = {k: overrides.get(k) or v for k, v in ATTENDANCE_SCHEMA_DEFAULTS.items()}
        else:
            leave_schema, attendance_schema = {}, {}
        bind.execute(
            sa.text("UPDATE leave_request_mappings SET kara_schema = CAST(:v AS JSON) WHERE id = :id"),
            {"v": json.dumps(leave_schema), "id": row.id},
        )
        bind.execute(
            sa.text("UPDATE attendance_mappings SET kara_schema = CAST(:v AS JSON) WHERE site_id = :site_id"),
            {"v": json.dumps(attendance_schema), "site_id": row.site_id},
        )

    op.drop_column("leave_request_mappings", "kara_writeback_enabled")


def downgrade() -> None:
    op.add_column(
        "leave_request_mappings",
        sa.Column("kara_writeback_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.drop_column("attendance_mappings", "kara_schema")
