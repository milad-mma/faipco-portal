"""Bind Web Push to authenticated device sessions (v9.3.3).

Revision ID: 153
Revises: 152

Intentionally NO legacy backfill: an endpoint alone cannot prove ownership of
an existing active session. Old subscriptions remain in DB but cannot receive
pushes until the logged-in device re-registers.
"""
from alembic import op
import sqlalchemy as sa

revision = "153"
down_revision = "152"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("push_subscriptions", sa.Column("session_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_push_subscriptions_session_id", "push_subscriptions", "user_sessions",
        ["session_id"], ["id"], ondelete="CASCADE",
    )
    op.create_index("ix_push_subscriptions_session_id", "push_subscriptions", ["session_id"])


def downgrade():
    op.drop_index("ix_push_subscriptions_session_id", table_name="push_subscriptions")
    op.drop_constraint("fk_push_subscriptions_session_id", "push_subscriptions", type_="foreignkey")
    op.drop_column("push_subscriptions", "session_id")
