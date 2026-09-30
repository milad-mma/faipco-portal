"""family module: family_profiles, family_members, family_documents, family_change_logs, permissions

Revision ID: 096
Revises: 095
Create Date: 2026-09-30

ماژول «مشخصات خانوادگی» (پایه‌ی حق تاهل و حق اولاد):
- family_profiles: یک پرونده برای هر پرسنل + وضعیت بررسی منابع انسانی + نسخه‌ی تأییدشده (JSON)
- family_members: همسر و فرزندان (پسر/دختر)
- family_documents: مدارک پیوست (bytea — در بکاپ pg_dump می‌ماند)
- family_change_logs: تاریخچه‌ی ثبت/تأیید/رد/بازگشایی
- مجوزها: family.view (فهرست، جزئیات، خروجی)، family.manage (تأیید/رد، سابقه بیمه، تنظیمات قواعد)

تنظیمات (فیلدها، مدارک، قواعد شمول) در system_settings با کلید family_settings ذخیره می‌شود.
مستقل از ماژول بیمه تکمیلی است.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "096"
down_revision: Union[str, None] = "095"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "family_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="draft"),
        sa.Column("marital_status", sa.String(16), nullable=True),
        sa.Column("marriage_date", sa.String(10), nullable=True),
        sa.Column("separation_date", sa.String(10), nullable=True),
        sa.Column("is_head_of_household", sa.Boolean(), nullable=True),
        sa.Column("has_children", sa.Boolean(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("reviewed_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("effective_date", sa.String(10), nullable=True),
        sa.Column("approved_data", sa.JSON(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("insurance_days", sa.Integer(), nullable=True),
        sa.Column("hr_note", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_family_profiles_status", "family_profiles", ["status"])
    op.create_table(
        "family_members",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("profile_id", sa.Integer(), sa.ForeignKey("family_profiles.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("member_type", sa.String(16), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("first_name", sa.String(100), nullable=False),
        sa.Column("last_name", sa.String(100), nullable=False),
        sa.Column("father_name", sa.String(100), nullable=True),
        sa.Column("national_id", sa.String(10), nullable=True),
        sa.Column("birth_certificate_no", sa.String(100), nullable=True),
        sa.Column("birth_date", sa.String(10), nullable=True),
        sa.Column("marriage_certificate_no", sa.String(100), nullable=True),
        sa.Column("mobile", sa.String(11), nullable=True),
        sa.Column("is_employed", sa.Boolean(), nullable=True),
        sa.Column("employer_name", sa.String(100), nullable=True),
        sa.Column("is_insured", sa.Boolean(), nullable=True),
        sa.Column("receives_child_allowance", sa.Boolean(), nullable=True),
        sa.Column("is_disabled", sa.Boolean(), nullable=True),
        sa.Column("relation", sa.String(16), nullable=True),
        sa.Column("other_parent_name", sa.String(100), nullable=True),
        sa.Column("custody", sa.String(16), nullable=True),
        sa.Column("is_student", sa.Boolean(), nullable=True),
        sa.Column("education_level", sa.String(100), nullable=True),
        sa.Column("school_name", sa.String(100), nullable=True),
        sa.Column("is_married", sa.Boolean(), nullable=True),
        sa.Column("marriage_date", sa.String(10), nullable=True),
    )
    op.create_table(
        "family_documents",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("profile_id", sa.Integer(), sa.ForeignKey("family_profiles.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("member_id", sa.Integer(), sa.ForeignKey("family_members.id", ondelete="SET NULL"), nullable=True, index=True),
        sa.Column("doc_type", sa.String(32), nullable=False),
        sa.Column("linked", sa.Boolean(), nullable=False, server_default=sa.false()),
        # مدرکی که پرسنل در ویرایش جدید حذف کرده ولی جزو نسخه‌ی تأییدشده است؛ تا تأیید بعدی نگه داشته می‌شود
        sa.Column("archived", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("file_name", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(100), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("data", sa.LargeBinary(), nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("uploaded_jalali", sa.String(10), nullable=True),
    )
    op.create_table(
        "family_change_logs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("profile_id", sa.Integer(), sa.ForeignKey("family_profiles.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("action", sa.String(32), nullable=False),
        sa.Column("actor_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("actor_name", sa.String(200), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("effective_date", sa.String(10), nullable=True),
        sa.Column("snapshot", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.execute(
        """
        INSERT INTO permissions (code, description) VALUES
        ('family.view', 'مشاهده مشخصات خانوادگی پرسنل، گزارش شمول حق تاهل/اولاد و خروجی Excel'),
        ('family.manage', 'تأیید/رد مشخصات خانوادگی، ثبت سابقه بیمه و تنظیم قواعد حق تاهل/اولاد')
        ON CONFLICT (code) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM role_permissions WHERE permission_id IN (SELECT id FROM permissions WHERE code IN ('family.view','family.manage'))")
    op.execute("DELETE FROM permissions WHERE code IN ('family.view','family.manage')")
    op.execute("DELETE FROM system_settings WHERE key = 'family_settings'")
    op.drop_table("family_change_logs")
    op.drop_table("family_documents")
    op.drop_table("family_members")
    op.drop_index("ix_family_profiles_status", table_name="family_profiles")
    op.drop_table("family_profiles")
