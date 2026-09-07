"""redesign evaluation site managers into flexible manager-assignment model

Revision ID: 054
Revises: 053
Create Date: 2026-09-07

طبق بازخورد صریح کاربر: طراحی قبلی فرض می‌کرد «مدیر سایت» همیشه *همه*
سرپرست‌های واحدها را خودکار ارزیابی می‌کند - ولی چارت سازمانی واقعی
شرکت‌ها این‌قدر ساده نیست (مثلاً یک مدیر میانی مثل «مدیر تولید» ممکن
است فقط بخشی از سرپرست‌ها را ارزیابی کند، یا لازم باشد یک فرد خاص از
یک واحد دیگر مستقیم به یک مدیر تخصیص داده شود).

این Migration:
    ۱. دو جدول جدید می‌سازد: evaluation_managers (مفهوم عمومی «مدیر»،
       جایگزین evaluation_site_managers) و evaluation_manager_assignments
       (تخصیص صریح و دستی اهداف هر مدیر).
    ۲. داده‌های موجود را مهاجرت می‌دهد - برای حفظ رفتار قبلی، هر مدیر
       سایتِ قدیمی، دقیقاً همان سرپرست‌های واحد + سایر مدیرانی که قبلاً
       به‌طور خودکار می‌دید را به‌صورت تخصیص صریح دریافت می‌کند - یعنی
       بعد از این Migration، هیچ داده‌ای گم نمی‌شود؛ فقط از این پس صریح
       (و قابل‌ویرایش) است، نه خودکار.
    ۳. دو جدول قدیمی (evaluation_site_managers، evaluation_other_managers)
       را حذف می‌کند - عملکردشان کاملاً در جدول‌های جدید جای گرفته است.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "054"
down_revision: Union[str, None] = "053"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "evaluation_managers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("site_id", "employee_id", name="uq_evaluation_manager"),
    )

    op.create_table(
        "evaluation_manager_assignments",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "manager_id", sa.Integer(), sa.ForeignKey("evaluation_managers.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column(
            "target_employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("manager_id", "target_employee_id", name="uq_evaluation_manager_target"),
    )

    # --- مهاجرت داده: evaluation_site_managers -> evaluation_managers ---
    op.execute(
        """
        INSERT INTO evaluation_managers (site_id, employee_id, title, created_at, updated_at)
        SELECT site_id, employee_id, NULL, created_at, updated_at
        FROM evaluation_site_managers
        """
    )

    # --- مهاجرت داده: رفتار قبلیِ خودکار «مدیر سایت = همه سرپرست‌های واحد» ---
    # حالا به‌صورت تخصیص صریح ذخیره می‌شود - قابل حذف/ویرایش، ولی چیزی گم نمی‌شود.
    op.execute(
        """
        INSERT INTO evaluation_manager_assignments (manager_id, target_employee_id, created_at, updated_at)
        SELECT DISTINCT m.id, eds.employee_id, now(), now()
        FROM evaluation_managers m
        JOIN departments d ON d.site_id = m.site_id
        JOIN evaluation_department_supervisors eds ON eds.department_id = d.id
        WHERE eds.employee_id != m.employee_id
        ON CONFLICT (manager_id, target_employee_id) DO NOTHING
        """
    )

    # --- مهاجرت داده: evaluation_other_managers -> تخصیص صریح برای همان مدیران سایت ---
    op.execute(
        """
        INSERT INTO evaluation_manager_assignments (manager_id, target_employee_id, created_at, updated_at)
        SELECT DISTINCT m.id, eom.employee_id, now(), now()
        FROM evaluation_managers m
        JOIN evaluation_other_managers eom ON eom.site_id = m.site_id
        WHERE eom.employee_id != m.employee_id
        ON CONFLICT (manager_id, target_employee_id) DO NOTHING
        """
    )

    op.drop_table("evaluation_other_managers")
    op.drop_table("evaluation_site_managers")


def downgrade() -> None:
    op.create_table(
        "evaluation_site_managers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("site_id", "employee_id", name="uq_evaluation_site_manager"),
    )
    op.create_table(
        "evaluation_other_managers",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("site_id", sa.Integer(), sa.ForeignKey("sites.id", ondelete="CASCADE"), nullable=False),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            onupdate=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint("site_id", "employee_id", name="uq_evaluation_other_manager"),
    )
    op.execute(
        """
        INSERT INTO evaluation_site_managers (site_id, employee_id, created_at, updated_at)
        SELECT site_id, employee_id, created_at, updated_at FROM evaluation_managers
        """
    )
    op.drop_table("evaluation_manager_assignments")
    op.drop_table("evaluation_managers")
