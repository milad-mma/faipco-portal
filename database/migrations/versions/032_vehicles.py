"""add vehicles table + حراست role/permission for reporting

Revision ID: 032
Revises: 031
Create Date: 2026-08-26

قابلیت «خودروهای من» — هر پرسنل می‌تواند یک یا چند خودرو برای خودش ثبت
کند. علاوه بر جدول اصلی، این Migration یک مجوز جدید (vehicles.view_all)
و یک نقش جدید («حراست») می‌سازد که این مجوز را دارد — چون در این پروژه
نقش‌ها/مجوزها هرگز از طریق کد ساخته نمی‌شوند (بدون Endpoint برای «ساخت
نقش جدید» — فقط تخصیص نقش‌های موجود)، این‌جا تنها جای درست برای این کار
است. بعد از این Migration، Admin از همان صفحه «کاربران/دسترسی‌ها» موجود
(که از قبل هر نقشی را که در جدول roles باشد نشان می‌دهد) نقش «حراست» را
به هرکسی که لازم است تخصیص می‌دهد — دقیقاً مثل بقیه نقش‌ها.

⚠️ عمداً `is_superuser` مسیر جداگانه دارد (همیشه دسترسی کامل، بدون نیاز
به این مجوز) — این مجوز فقط برای پرسنل غیر-Admin با نقش «حراست» است که
فقط اجازه **مشاهده/گزارش‌گیری** (نه ویرایش/حذف) دارند.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "032"
down_revision: Union[str, None] = "031"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "vehicles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("vehicle_type", sa.String(length=100), nullable=False),
        sa.Column("color", sa.String(length=50), nullable=False),
        sa.Column("plate_digits1", sa.String(length=2), nullable=False),
        sa.Column("plate_letter", sa.String(length=1), nullable=False),
        sa.Column("plate_digits2", sa.String(length=3), nullable=False),
        sa.Column("plate_iran_code", sa.String(length=2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_vehicles_employee_id", "vehicles", ["employee_id"])

    # مجوز جدید — فقط اگر از قبل نبود (اجرای دوباره این Migration را ایمن نگه می‌دارد)
    op.execute(
        """
        INSERT INTO permissions (code, description)
        VALUES ('vehicles.view_all', 'مشاهده و گزارش‌گیری از خودروهای همه پرسنل (فقط خواندن)')
        ON CONFLICT (code) DO NOTHING
        """
    )
    # مجوز ویرایش/حذف — دقیقاً هم‌الگو با sites.manage در بقیه پروژه: به
    # هیچ نقشی متصل نمی‌شود (یعنی فقط Admin واقعی — is_superuser — از طریق
    # همان مسیر میان‌بر داخل require_permission() اجازه دارد)؛ وجودش در
    # جدول permissions فقط برای این است که اگر روزی خواستند به یک نقش
    # دیگر هم بدهند، ردیفش از قبل آماده باشد.
    op.execute(
        """
        INSERT INTO permissions (code, description)
        VALUES ('vehicles.manage', 'ویرایش/حذف خودروهای هر پرسنلی (فقط Admin)')
        ON CONFLICT (code) DO NOTHING
        """
    )

    # نقش جدید «حراست»
    op.execute(
        """
        INSERT INTO roles (name, description, is_system, created_at, updated_at)
        VALUES ('حراست', 'دسترسی فقط‌خواندنی به گزارش خودروهای پرسنل', false, now(), now())
        ON CONFLICT (name) DO NOTHING
        """
    )

    # اتصال نقش «حراست» به مجوز vehicles.view_all
    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT r.id, p.id
        FROM roles r, permissions p
        WHERE r.name = 'حراست' AND p.code = 'vehicles.view_all'
        ON CONFLICT (role_id, permission_id) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM role_permissions WHERE role_id IN (SELECT id FROM roles WHERE name = 'حراست')")
    op.execute("DELETE FROM roles WHERE name = 'حراست'")
    op.execute("DELETE FROM permissions WHERE code IN ('vehicles.view_all', 'vehicles.manage')")
    op.drop_index("ix_vehicles_employee_id", table_name="vehicles")
    op.drop_table("vehicles")
