"""اتوماسیون اداری فاز ۳ب: امضای شخصی

- oa_signature_versions (نسخه‌دار؛ یک active برای هر نفر)
- oa_letters: sign_on_send، signature_version_id، signer_*، signed_at

Revision ID: 144
Revises: 143
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "144"
down_revision: Union[str, None] = "143"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "oa_signature_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_employee_id", sa.Integer(), sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_no", sa.Integer(), nullable=False),
        sa.Column("file_id", sa.Integer(), sa.ForeignKey("oa_files.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("method", sa.String(8), nullable=False),
        sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        sa.Column("created_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deactivated_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deactivate_reason", sa.String(300), nullable=True),
        sa.UniqueConstraint("owner_employee_id", "version_no", name="uq_oa_signature_version"),
    )
    op.create_index("ix_oa_signature_versions_owner_employee_id", "oa_signature_versions", ["owner_employee_id"])
    # حداکثر یک امضای فعال برای هر نفر
    op.execute(
        "CREATE UNIQUE INDEX uq_oa_signature_one_active ON oa_signature_versions (owner_employee_id) WHERE status = 'active'"
    )
    op.add_column("oa_letters", sa.Column("sign_on_send", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("oa_letters", sa.Column("signature_version_id", sa.Integer(),
                                          sa.ForeignKey("oa_signature_versions.id", ondelete="RESTRICT"), nullable=True))
    op.add_column("oa_letters", sa.Column("signer_employee_id", sa.Integer(),
                                          sa.ForeignKey("employees.id", ondelete="SET NULL"), nullable=True))
    op.add_column("oa_letters", sa.Column("signer_name_snapshot", sa.String(200), nullable=True))
    op.add_column("oa_letters", sa.Column("signer_title_snapshot", sa.String(200), nullable=True))
    op.add_column("oa_letters", sa.Column("signed_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    for col in ("signed_at", "signer_title_snapshot", "signer_name_snapshot", "signer_employee_id",
                "signature_version_id", "sign_on_send"):
        op.drop_column("oa_letters", col)
    op.execute("DROP INDEX IF EXISTS uq_oa_signature_one_active")
    op.drop_index("ix_oa_signature_versions_owner_employee_id", table_name="oa_signature_versions")
    op.drop_table("oa_signature_versions")
