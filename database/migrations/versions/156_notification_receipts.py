"""Record client confirmations independently of provider acceptance."""
from alembic import op
import sqlalchemy as sa

revision = "156"
down_revision = "155"
branch_labels = None
depends_on = None


def upgrade():
    for name in ("received_at", "opened_at"):
        op.add_column("push_dispatch_deliveries", sa.Column(name, sa.DateTime(timezone=True)))
    op.create_table(
        "oa_push_receipts",
        sa.Column("event_id", sa.Integer(), sa.ForeignKey("oa_notification_outbox.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("subscription_id", sa.Integer(), primary_key=True),
        sa.Column("session_id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True)),
    )


def downgrade():
    op.drop_table("oa_push_receipts")
    for name in ("opened_at", "received_at"):
        op.drop_column("push_dispatch_deliveries", name)
