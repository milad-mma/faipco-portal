"""درخواست «مجوز خروج»، محدودیت مرخصی ساعتی به شیفت و تلرانس تطبیق تردد (docs/leave-requests.md)

Revision ID: 117
Revises: 116

- leave_request_types.is_exit_permit: نوعی که فقط ساعت خروج (بعد از پایان شیفت) ثبت می‌کند؛ مرخصی/مأموریت ثبت نمی‌شود،
  فقط سرپرست تأیید می‌کند و در کاراوب مثل خودش (OperationsID=2، ActionId=14، Card_No=307، StartHour=EndHour، مدت ۰،
  AcceptCode=0 با تأیید) بدون نوشتن در تردد/کارکرد ثبت می‌شود.
- leave_request_mappings.punch_tolerance_minutes (پیش‌فرض ۳۰، مثل WF_TL فعلی کاراوب): تلرانس تطبیق تردد با درخواست
  ساعتی؛ نگاشت ستون‌های IOTime/Tolerance درخواست برای سایت‌هایی که AcceptCode را نگاشت کرده‌اند اضافه می‌شود.
- برای سایت‌هایی که نوع درخواست دارند: نوع کارت ۳۰۷ موجود علامت می‌خورد، وگرنه نوع «مجوز خروج» ساخته می‌شود
  (به‌همراه مجوز مشاهده‌ی عنوانش برای حراست).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "117"
down_revision: Union[str, None] = "116"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "leave_request_mappings",
        sa.Column("punch_tolerance_minutes", sa.Integer(), nullable=False, server_default="30"),
    )
    op.execute(
        """
        UPDATE leave_request_mappings
        SET kara_schema = (kara_schema::jsonb
            || '{"wf_requests.io_time": "IOTime", "wf_requests.tolerance": "Tolerance"}'::jsonb)::json
        WHERE kara_schema::jsonb ? 'wf_requests.accept_code'
        """
    )
    op.add_column(
        "leave_request_types",
        sa.Column("is_exit_permit", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.execute("UPDATE leave_request_types SET is_exit_permit = TRUE WHERE card_no = 307")
    op.execute(
        """
        INSERT INTO leave_request_types
            (site_id, title, is_mission, is_hourly, is_active, action_id, operation_id, card_no,
             is_forgotten_punch, is_exit_permit, created_at, updated_at)
        SELECT DISTINCT t.site_id, 'مجوز خروج', FALSE, TRUE, TRUE, 14, 2, 307, FALSE, TRUE, now(), now()
        FROM leave_request_types t
        WHERE NOT EXISTS (
            SELECT 1 FROM leave_request_types x WHERE x.site_id = t.site_id AND x.card_no = 307
        )
        """
    )
    op.execute(
        """
        INSERT INTO permissions (code, description)
        VALUES ('leave_requests.view.type.مجوز_خروج', 'مشاهده درخواست‌های «مجوز خروج»')
        ON CONFLICT (code) DO NOTHING
        """
    )


def downgrade() -> None:
    op.drop_column("leave_request_types", "is_exit_permit")
    op.drop_column("leave_request_mappings", "punch_tolerance_minutes")
