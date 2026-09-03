"""add customizable password reset email templates to smtp_settings

Revision ID: 047
Revises: 046
Create Date: 2026-09-02

عنوان و متن ایمیل «فراموشی رمز عبور» قابل‌شخصی‌سازی می‌شود - {reset_link}
در متن، با لینک واقعی بازنشانی (حاوی توکن) جایگزین می‌شود. اگر خالی
بمانند، یک قالب پیش‌فرض معقول در password_reset_service.py استفاده می‌شود.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "047"
down_revision: Union[str, None] = "046"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("smtp_settings", sa.Column("password_reset_email_subject", sa.String(length=255), nullable=True))
    op.add_column("smtp_settings", sa.Column("password_reset_email_body", sa.String(length=4000), nullable=True))


def downgrade() -> None:
    op.drop_column("smtp_settings", "password_reset_email_body")
    op.drop_column("smtp_settings", "password_reset_email_subject")
