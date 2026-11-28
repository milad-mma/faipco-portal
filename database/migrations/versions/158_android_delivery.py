"""Per-install permissions and session-bound native notification inbox."""
from alembic import op
import sqlalchemy as sa

revision = "158"
down_revision = "157"
branch_labels = depends_on = None


def upgrade():
    for name in ("perm_coarse_location", "keep_permissions"):
        op.add_column("mobile_devices", sa.Column(name, sa.Boolean()))
    for name in ("mobile_devices", "device_pairing_codes"):
        op.add_column(name, sa.Column("session_sid", sa.String(36)))
    op.create_index("ix_mobile_devices_session_sid", "mobile_devices", ["session_sid"])
    op.add_column("push_subscriptions", sa.Column("native_device_id", sa.Integer(),
                  sa.ForeignKey("mobile_devices.id", ondelete="CASCADE")))
    op.create_table("android_notification_inbox",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("device_id", sa.Integer(), sa.ForeignKey("mobile_devices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("subscription_id", sa.Integer(), nullable=False),
        sa.Column("session_id", sa.Integer(), nullable=False),
        sa.Column("event_key", sa.String(255), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("state", sa.String(16), nullable=False),
        sa.Column("lease_until", sa.DateTime(timezone=True)),
        sa.UniqueConstraint("event_key", "subscription_id", "session_id"))
    op.create_index("ix_android_inbox_device", "android_notification_inbox", ["device_id", "session_id", "state"])


def downgrade():
    op.drop_table("android_notification_inbox")
    op.drop_column("push_subscriptions", "native_device_id")
    op.drop_index("ix_mobile_devices_session_sid", table_name="mobile_devices")
    op.drop_column("device_pairing_codes", "session_sid")
    for name in ("session_sid", "keep_permissions", "perm_coarse_location"):
        op.drop_column("mobile_devices", name)
