"""Persist browser readiness without changing existing subscription eligibility.

Revision ID: 155
Revises: 154
NULL retains the legacy registration/grace behavior. No event backfill.
"""
from alembic import op
import sqlalchemy as sa

revision = "155"
down_revision = "154"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("push_subscriptions", sa.Column("client_ready", sa.Boolean(), nullable=True))


def downgrade():
    op.drop_column("push_subscriptions", "client_ready")
