"""Dedicated global HR permission for sensitive recruitment records.

Revision ID: 151
Revises: 150
"""
from alembic import op
revision = "151"
down_revision = "150"
branch_labels = None
depends_on = None

def upgrade():
    op.execute("INSERT INTO permissions (code, description) VALUES ('careers.manage', 'استخدام: مدیریت درخواست‌ها، مشاهده اطلاعات حساس، چاپ و ویرایش صفحه عمومی') ON CONFLICT (code) DO NOTHING")

def downgrade():
    op.execute("DELETE FROM user_permissions WHERE permission_id IN (SELECT id FROM permissions WHERE code='careers.manage')")
    op.execute("DELETE FROM role_permissions WHERE permission_id IN (SELECT id FROM permissions WHERE code='careers.manage')")
    op.execute("DELETE FROM permissions WHERE code='careers.manage'")
