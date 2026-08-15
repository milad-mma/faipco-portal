"""performance: add missing indexes on high-traffic FK/filter columns (بهینه‌سازی سرعت — رفع Full Table Scan روی جدول‌های پرترافیک)

Revision ID: 022
Revises: 021
Create Date: 2026-08-16

بررسی کامل مدل‌ها نشان داد اکثر Foreign Key های این پروژه هیچ Index ای
ندارند (PostgreSQL برخلاف بعضی دیتابیس‌های دیگر، برای FK خودکار Index
نمی‌سازد). چند تا از این‌ها روی UniqueConstraint های چندستونی به‌طور ضمنی
Index دارند (فقط برای ستون اول آن Constraint)، ولی خیلی از ستون‌های واقعاً
پرترافیک اصلاً هیچ Index ای ندارند — یعنی هر کوئری روی آن‌ها یک
Full Table Scan است که با رشد داده‌ها هرروز کندتر می‌شود.

مهم‌ترین مورد: notice_targets.notice_id — چون زیربنای همان Subquery ای
است که تقریباً روی هر بار باز کردن صفحه اطلاعیه‌ها توسط هر کاربر اجرا می‌شود.

از CREATE INDEX IF NOT EXISTS (نه پارامتر if_not_exists خودِ Alembic)
استفاده شده — تا مستقل از نسخه دقیق Alembic نصب‌شده، همیشه Idempotent و
بی‌خطر برای اجرای مجدد باشد.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "022"
down_revision: Union[str, None] = "021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# (نام Index، جدول، ستون‌ها)
_INDEXES = [
    # اطلاعیه‌ها — پرترافیک‌ترین بخش کل پروژه (هر کاربر، هر بار)
    ("ix_notice_targets_notice_id", "notice_targets", ["notice_id"]),
    ("ix_notice_targets_type_id", "notice_targets", ["target_type", "target_id"]),
    ("ix_notices_status", "notices", ["status"]),
    ("ix_notices_is_deleted", "notices", ["is_deleted"]),
    ("ix_notice_reads_user_id", "notice_reads", ["user_id"]),
    # فیش حقوقی/فیش کارکرد — چک‌کردن «آیا این کاربر فیش خودش را دارد؟»
    ("ix_payroll_receipts_employee_id", "payroll_receipts", ["employee_id"]),
    ("ix_attendance_card_receipts_employee_id", "attendance_card_receipts", ["employee_id"]),
    # پرسنل — فیلتر/Join پرکاربرد در تقریباً همه صفحات مدیریتی
    ("ix_employees_site_id", "employees", ["site_id"]),
    ("ix_employees_department_id", "employees", ["department_id"]),
    ("ix_departments_supervisor_user_id", "departments", ["supervisor_user_id"]),
    # کاربران/Push — هر ارسال Push نیاز به این Lookup دارد
    ("ix_users_employee_id", "users", ["employee_id"]),
    ("ix_push_subscriptions_user_id", "push_subscriptions", ["user_id"]),
    # گزارش Sync هر سایت
    ("ix_sync_logs_site_id", "sync_logs", ["site_id"]),
]


def upgrade() -> None:
    for index_name, table_name, columns in _INDEXES:
        cols_sql = ", ".join(columns)
        op.execute(f'CREATE INDEX IF NOT EXISTS {index_name} ON {table_name} ({cols_sql})')


def downgrade() -> None:
    for index_name, _table_name, _columns in reversed(_INDEXES):
        op.execute(f'DROP INDEX IF EXISTS {index_name}')
