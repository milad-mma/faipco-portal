"""Transactional OA notification outbox and immutable snapshots for new letter versions.

Revision ID: 152
Revises: 151
"""
from alembic import op
import sqlalchemy as sa

revision = "152"
down_revision = "151"
branch_labels = None
depends_on = None


def upgrade():
    # Existing historical versions cannot be reliably reconstructed: do not
    # backfill them from the letter's CURRENT recipients/approval path.
    op.add_column("oa_letter_versions", sa.Column("recipients_snapshot", sa.JSON(), nullable=True))
    op.add_column("oa_letter_versions", sa.Column("approval_plan_snapshot", sa.JSON(), nullable=True))
    op.create_table(
        "oa_notification_outbox",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(200), nullable=False, unique=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_oa_notification_outbox_status", "oa_notification_outbox", ["status"])
    op.create_index("ix_oa_notification_outbox_pending", "oa_notification_outbox", ["status", "next_attempt_at"])


def downgrade():
    op.drop_index("ix_oa_notification_outbox_pending", table_name="oa_notification_outbox")
    op.drop_index("ix_oa_notification_outbox_status", table_name="oa_notification_outbox")
    op.drop_table("oa_notification_outbox")
    op.drop_column("oa_letter_versions", "approval_plan_snapshot")
    op.drop_column("oa_letter_versions", "recipients_snapshot")
