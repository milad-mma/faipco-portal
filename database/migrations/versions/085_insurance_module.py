"""insurance module: registrations, members, documents, permissions

Revision ID: 085
Revises: 084
Create Date: 2026-09-23

بازسازی سامانه ثبت‌نام بیمه تکمیلی (insurance.faipco.ir - PHP/MySQL) داخل
پرتال، با همان فیلدها و همان منطق فرم. داده قدیمی منتقل نمی‌شود.

- insurance_registrations: یک ردیف برای هر پرسنل (شخص اصلی؛ RelationCode=1 قدیمی)
- insurance_members: اعضای خانواده هر ثبت‌نام (همسر/پدر/مادر/پسر/دختر)
- insurance_documents: مدرک کفالت/حضانت هر عضو (bytea - در بکاپ pg_dump می‌ماند)
- مجوزها: insurance.view (فهرست/خروجی)، insurance.manage (تنظیمات/حذف)
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "085"
down_revision: Union[str, None] = "084"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "insurance_registrations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, unique=True),
        # عکس‌برداری از اطلاعات پرسنل در لحظه ثبت (خروجی Excel باید همان مقادیر ثبت‌شده را بدهد)
        sa.Column("personnel_code", sa.String(64), nullable=False),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("father_name", sa.String(100), nullable=False),
        sa.Column("birth_date", sa.String(10), nullable=False),
        sa.Column("gender", sa.SmallInteger(), nullable=False),
        sa.Column("marital_status", sa.SmallInteger(), nullable=False),
        sa.Column("national_id", sa.String(10), nullable=False),
        sa.Column("birth_certificate_no", sa.String(20), nullable=False),
        sa.Column("mobile_number", sa.String(11), nullable=False),
        sa.Column("employment_date", sa.String(10), nullable=False),
        sa.Column("insurance_no", sa.String(10), nullable=False),
        sa.Column("bank_code", sa.SmallInteger(), nullable=False),
        sa.Column("account_number", sa.String(40), nullable=False),
        sa.Column("sheba", sa.String(24), nullable=False),
        sa.Column("account_type", sa.SmallInteger(), nullable=False),
        sa.Column("account_owner", sa.String(200), nullable=False),
        sa.Column("account_owner_national_id", sa.String(10), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "insurance_members",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("registration_id", sa.Integer(), sa.ForeignKey("insurance_registrations.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("member_type", sa.String(16), nullable=False),  # spouse/son/daughter/father/mother
        sa.Column("relation_code", sa.SmallInteger(), nullable=False),
        sa.Column("dependency_code", sa.SmallInteger(), nullable=False),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("father_name", sa.String(100), nullable=False),
        sa.Column("birth_date", sa.String(10), nullable=False),
        sa.Column("gender", sa.SmallInteger(), nullable=False),
        sa.Column("marital_status", sa.SmallInteger(), nullable=False),
        sa.Column("national_id", sa.String(10), nullable=False),
        sa.Column("birth_certificate_no", sa.String(20), nullable=False),
        sa.Column("mobile_number", sa.String(11), nullable=False),
        # وضعیت کفالت: NULL = پرسیده نشده، 'yes'/'no'
        sa.Column("kafala_status", sa.String(3), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_table(
        "insurance_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("member_id", sa.Integer(), sa.ForeignKey("insurance_members.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("data", sa.LargeBinary(), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.execute(
        """
        INSERT INTO permissions (code, description) VALUES
        ('insurance.view', 'مشاهده فهرست ثبت‌نام‌های بیمه تکمیلی و خروجی Excel'),
        ('insurance.manage', 'تنظیمات بیمه تکمیلی (فعال/غیرفعال، نرخ‌ها، توضیحات) و حذف ثبت‌نام')
        ON CONFLICT (code) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM role_permissions WHERE permission_id IN (SELECT id FROM permissions WHERE code IN ('insurance.view','insurance.manage'))")
    op.execute("DELETE FROM permissions WHERE code IN ('insurance.view','insurance.manage')")
    op.drop_table("insurance_documents")
    op.drop_table("insurance_members")
    op.drop_table("insurance_registrations")
