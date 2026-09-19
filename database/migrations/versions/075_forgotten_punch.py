"""forgotten punch: request type flag, per-site HR officer, extra Kara names

Revision ID: 075
Revises: 074
Create Date: 2026-09-19

تردد فراموش‌شده (طبق درخواست کاربر):
  - leave_request_types.is_forgotten_punch
  - leave_request_hr_officers: مسئول نیروی انسانی هر سایت (تأییدکننده نهایی)
  - نام‌های تازه کاراوب (ستون‌های Modify/Direction/VT/AC جدول تردد و ستون‌های
    جدول ارجاع WF_MoveUp) فقط برای سایت‌هایی اضافه می‌شوند که گروه مربوطش
    از قبل نگاشت شده است - تا رفتار سایت‌های نگاشت‌نشده عوض نشود.
  - نوع «تردد فراموش شده» (کارت ۳۰۵، ActionId ۸، OperationsID ۲ - مقادیر
    واقعی کاراوب) برای سایت‌هایی که نگاشت مرخصی/ماموریت دارند ساخته می‌شود.
"""
import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "075"
down_revision: Union[str, None] = "074"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

TYPE_TITLE = "تردد فراموش شده"
PERMISSION_CODE = "leave_requests.view.type.تردد_فراموش_شده"

DATAFILE_EXTRA = {
    "datafile.modify": "Modify",
    "datafile.direction": "Direction",
    "datafile.vt": "VT",
    "datafile.ac": "AC",
}
MOVEUP_EXTRA = {
    "wf_moveup.date": "DateMoveUp",
    "wf_moveup.from_manager": "FromManagerEmp_No",
    "wf_moveup.to_manager": "ToManagerEmp_No",
    "wf_moveup.card_no": "CardNo",
    "wf_moveup.from_sec": "FromSec_No",
    "wf_moveup.to_sec": "ToSec_No",
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
    op.add_column(
        "leave_request_types",
        sa.Column("is_forgotten_punch", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.create_table(
        "leave_request_hr_officers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )

    bind = op.get_bind()
    for row in bind.execute(sa.text("SELECT id, kara_schema FROM attendance_mappings")).fetchall():
        schema = _as_dict(row.kara_schema)
        if schema.get("datafile.status"):
            for key, value in DATAFILE_EXTRA.items():
                schema.setdefault(key, value)
            bind.execute(
                sa.text("UPDATE attendance_mappings SET kara_schema = CAST(:v AS JSON) WHERE id = :id"),
                {"v": json.dumps(schema), "id": row.id},
            )

    leave_rows = bind.execute(sa.text("SELECT id, site_id, kara_schema FROM leave_request_mappings")).fetchall()
    for row in leave_rows:
        schema = _as_dict(row.kara_schema)
        if schema.get("wf_moveup.request_id"):
            for key, value in MOVEUP_EXTRA.items():
                schema.setdefault(key, value)
            bind.execute(
                sa.text("UPDATE leave_request_mappings SET kara_schema = CAST(:v AS JSON) WHERE id = :id"),
                {"v": json.dumps(schema), "id": row.id},
            )
        exists = bind.execute(
            sa.text("SELECT 1 FROM leave_request_types WHERE site_id = :s AND (is_forgotten_punch OR card_no = 305)"),
            {"s": row.site_id},
        ).first()
        if not exists:
            bind.execute(
                sa.text(
                    "INSERT INTO leave_request_types (site_id, title, is_mission, is_hourly, is_active, action_id, "
                    "operation_id, card_no, is_forgotten_punch) VALUES (:s, :t, false, true, true, 8, 2, 305, true)"
                ),
                {"s": row.site_id, "t": TYPE_TITLE},
            )

    if leave_rows:
        exists = bind.execute(sa.text("SELECT 1 FROM permissions WHERE code = :c"), {"c": PERMISSION_CODE}).first()
        if not exists:
            bind.execute(
                sa.text("INSERT INTO permissions (code, description) VALUES (:c, :d)"),
                {"c": PERMISSION_CODE, "d": f"مشاهده درخواست‌های «{TYPE_TITLE}»"},
            )


def downgrade() -> None:
    op.drop_table("leave_request_hr_officers")
    op.drop_column("leave_request_types", "is_forgotten_punch")
