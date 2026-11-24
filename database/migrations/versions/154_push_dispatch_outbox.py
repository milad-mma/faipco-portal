"""Durable Web Push dispatch jobs and per-device delivery history.

Revision ID: 154
Revises: 153
No historical backfill or re-send of existing notices.
"""
from alembic import op
import sqlalchemy as sa

revision = "154"
down_revision = "153"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "push_dispatch_jobs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key", sa.String(100), nullable=False, unique=True),
        sa.Column("origin", sa.String(255), nullable=False),
        sa.Column("notice_id", sa.Integer(), sa.ForeignKey("notices.id", ondelete="CASCADE")),
        sa.Column("user_ids", sa.JSON()),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("priority", sa.String(20), nullable=False),
        sa.Column("notice_type", sa.String(30), nullable=False),
        sa.Column("body", sa.Text()),
        sa.Column("status", sa.String(24), nullable=False, server_default="pending"),
        sa.Column("initialized", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("target_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("no_device_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("deadline_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.String(120)),
    )
    op.create_index("ix_push_dispatch_jobs_notice_id", "push_dispatch_jobs", ["notice_id"])
    op.create_index("ix_push_dispatch_jobs_due", "push_dispatch_jobs", ["origin", "status", "next_attempt_at"])
    op.create_table(
        "push_dispatch_deliveries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("job_id", sa.Integer(), sa.ForeignKey("push_dispatch_jobs.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subscription_id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(24), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True)),
        sa.Column("last_error", sa.String(120)),
        sa.UniqueConstraint("job_id", "subscription_id", "session_id", name="uq_push_dispatch_job_subscription"),
    )
    op.create_index("ix_push_dispatch_deliveries_due", "push_dispatch_deliveries", ["job_id", "status", "next_attempt_at"])


def downgrade():
    op.drop_table("push_dispatch_deliveries")
    op.drop_table("push_dispatch_jobs")
