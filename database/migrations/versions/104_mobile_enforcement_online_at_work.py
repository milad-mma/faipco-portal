"""اپ اندروید: «آنلاین در محیط کار»، زمان ضددستکاری و ادغام مجوزهای حضور

Revision ID: 104
Revises: 103
Create Date: 2026-10-06

- presence_sessions.source: «portal» (پرتال باز، WebSocket) یا «background» (اپ بسته؛ آنلاین شدن گوشی داخل محدوده
  که بخش بومی اپ گزارش می‌دهد). presence_sessions.time_uncertain برای نشست پس‌زمینه‌ای که زمانش قابل محاسبه نبود.
- gps_activity_logs.time_uncertain و geofence_events.time_uncertain: گوشی بین رویداد و ارسال خاموش/روشن شده و زمان
  با «کرنومتر» گوشی قابل محاسبه نبود (به‌جایش ساعت گوشی).
- مجوزها: attendance.clock_in_out (ثبت دستی ورود/خروج — حذف شد)، attendance.view_logs و
  attendance.view_clock_records حذف می‌شوند؛ نقش‌هایی که یکی از دو مجوز مشاهده را داشتند attendance.manage_clock_records
  می‌گیرند تا دسترسی به گزارش‌ها از دست نرود (به انتخاب کاربر، مشاهده و ویرایش دستی یک مجوز شدند). نقش آزمایشی
  «attendance-pilot» این مجوز را نمی‌گیرد و اگر مجوز دیگری ندارد حذف می‌شود.
- downgrade ستون‌ها را برمی‌دارد و مجوزهای حذف‌شده را (بدون انتساب به نقش‌ها) دوباره می‌سازد؛ انتساب‌های قبلی و نقش
  attendance-pilot برنمی‌گردند (یک‌طرفه).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "104"
down_revision: Union[str, None] = "103"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

REMOVED = ("attendance.clock_in_out", "attendance.view_logs", "attendance.view_clock_records")


def upgrade() -> None:
    op.add_column(
        "presence_sessions", sa.Column("source", sa.String(16), nullable=False, server_default="portal")
    )
    op.add_column(
        "presence_sessions", sa.Column("time_uncertain", sa.Boolean(), nullable=False, server_default=sa.false())
    )
    op.add_column(
        "gps_activity_logs", sa.Column("time_uncertain", sa.Boolean(), nullable=False, server_default=sa.false())
    )
    op.add_column(
        "geofence_events", sa.Column("time_uncertain", sa.Boolean(), nullable=False, server_default=sa.false())
    )
    # پیدا کردن نشست پس‌زمینه‌ی باز یک پرسنل در یک سایت (هر رویداد اپ)
    op.create_index(
        "ix_presence_sessions_background_open",
        "presence_sessions",
        ["employee_id", "matched_site_id"],
        postgresql_where=sa.text("source = 'background' AND disconnected_at IS NULL"),
    )

    # مشاهده‌ی گزارش‌ها به manage_clock_records منتقل می‌شود
    op.execute(
        """
        INSERT INTO permissions (code, description) VALUES
        ('attendance.manage_clock_records', 'گزارش ورود/خروج و «آنلاین در محیط کار» پرسنل، و افزودن/ویرایش/حذف دستی رکورد ورود/خروج')
        ON CONFLICT (code) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT DISTINCT rp.role_id, (SELECT id FROM permissions WHERE code = 'attendance.manage_clock_records')
        FROM role_permissions rp
        JOIN permissions p ON p.id = rp.permission_id
        JOIN roles r ON r.id = rp.role_id
        WHERE p.code IN ('attendance.view_logs', 'attendance.view_clock_records')
          AND r.name <> 'attendance-pilot'
          AND NOT EXISTS (
              SELECT 1 FROM role_permissions x
              WHERE x.role_id = rp.role_id
                AND x.permission_id = (SELECT id FROM permissions WHERE code = 'attendance.manage_clock_records')
          )
        """
    )
    op.execute(
        """
        UPDATE permissions
        SET description = 'گزارش ورود/خروج و «آنلاین در محیط کار» پرسنل، و افزودن/ویرایش/حذف دستی رکورد ورود/خروج'
        WHERE code = 'attendance.manage_clock_records'
        """
    )
    codes = ", ".join(f"'{c}'" for c in REMOVED)
    op.execute(f"DELETE FROM role_permissions WHERE permission_id IN (SELECT id FROM permissions WHERE code IN ({codes}))")
    op.execute(f"DELETE FROM permissions WHERE code IN ({codes})")
    # نقش آزمایشی که حالا هیچ مجوزی ندارد
    op.execute(
        """
        DELETE FROM user_roles WHERE role_id IN (
            SELECT r.id FROM roles r
            WHERE r.name = 'attendance-pilot'
              AND NOT EXISTS (SELECT 1 FROM role_permissions rp WHERE rp.role_id = r.id)
        )
        """
    )
    op.execute(
        """
        DELETE FROM roles r
        WHERE r.name = 'attendance-pilot'
          AND NOT EXISTS (SELECT 1 FROM role_permissions rp WHERE rp.role_id = r.id)
        """
    )


def downgrade() -> None:
    op.execute(
        """
        INSERT INTO permissions (code, description) VALUES
        ('attendance.clock_in_out', 'ثبت ورود/خروج آزمایشی مبتنی بر GPS'),
        ('attendance.view_logs', 'مشاهده گزارش «پرسنل آنلاین»'),
        ('attendance.view_clock_records', 'مشاهده گزارش ورود/خروج آزمایشی GPS همه پرسنل')
        ON CONFLICT (code) DO NOTHING
        """
    )
    op.drop_index("ix_presence_sessions_background_open", table_name="presence_sessions")
    op.drop_column("geofence_events", "time_uncertain")
    op.drop_column("gps_activity_logs", "time_uncertain")
    op.drop_column("presence_sessions", "time_uncertain")
    op.drop_column("presence_sessions", "source")
