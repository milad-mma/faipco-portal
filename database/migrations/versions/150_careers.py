"""Recruitment applications and public careers page copy.

Revision ID: 150
Revises: 149
"""
from alembic import op
import sqlalchemy as sa

revision = "150"
down_revision = "149"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("career_page_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("title", sa.String(180), nullable=False),
        sa.Column("introduction", sa.Text(), nullable=False),
        sa.Column("instructions", sa.Text(), nullable=False),
        sa.Column("is_open", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("updated_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_table("career_applications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("full_name", sa.String(160), nullable=False),
        sa.Column("mobile", sa.String(16), nullable=False),
        sa.Column("requested_position", sa.String(160), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="new"),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("hr_note", sa.Text()),
        sa.Column("changed_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL")),
        sa.Column("ip_digest", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.create_index("ix_career_applications_status", "career_applications", ["status"])
    op.create_index("ix_career_applications_ip_digest", "career_applications", ["ip_digest"])
    op.create_index("ix_career_applications_created_at", "career_applications", ["created_at"])
    op.execute("INSERT INTO career_page_settings (id,title,introduction,instructions,is_open) VALUES (1,'همکاری با فواد الیاف','از علاقه‌مندان به همکاری با شرکت فواد الیاف دعوت می‌کنیم درخواست استخدام خود را از طریق فرم زیر ثبت کنند.','لطفاً اطلاعات را صحیح و کامل وارد کنید. تکمیل فرم به معنی تعهد شرکت به استخدام نیست.',true)")


def downgrade():
    op.drop_table("career_applications")
    op.drop_table("career_page_settings")
