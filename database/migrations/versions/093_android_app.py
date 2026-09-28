"""اپ اندروید: گوشی‌های متصل، کد اتصال، رویدادهای Geofencing، معافیت‌ها، نسخه‌های APK و منبع لاگ GPS

Revision ID: 093
Revises: 092
Create Date: 2026-09-28

- mobile_devices / device_pairing_codes / geofence_events / mobile_app_exemptions / mobile_app_releases
- gps_activity_logs.source (web | manual | geofence) و device_id؛ رکوردهای دستی قبلی source=manual می‌گیرند.
- مجوزها: mobile.devices (سایت‌محور: دستگاه‌ها، معافیت‌ها، رویدادها) و system.mobile_app (کل سیستم: تنظیمات و APK).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "093"
down_revision: Union[str, None] = "092"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "mobile_devices",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("employee_id", sa.Integer, sa.ForeignKey("employees.id", ondelete="SET NULL"), nullable=True),
        sa.Column("device_uid", sa.String(64), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("manufacturer", sa.String(60)),
        sa.Column("model", sa.String(80)),
        sa.Column("os_version", sa.String(20)),
        sa.Column("sdk_int", sa.Integer),
        sa.Column("app_version_code", sa.Integer),
        sa.Column("app_version_name", sa.String(30)),
        sa.Column("has_gms", sa.Boolean),
        sa.Column("geofence_engine", sa.String(20)),
        sa.Column("perm_fine_location", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("perm_background_location", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("perm_notifications", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("battery_unrestricted", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("location_enabled", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("geofences_registered", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("geofence_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status_reported_at", sa.DateTime(timezone=True)),
        sa.Column("last_event_at", sa.DateTime(timezone=True)),
        sa.Column("last_ip", sa.String(64)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_reason", sa.String(120)),
    )
    op.create_index("ix_mobile_devices_user_id", "mobile_devices", ["user_id"])
    op.create_index("ix_mobile_devices_employee_id", "mobile_devices", ["employee_id"])
    op.create_index("ix_mobile_devices_device_uid", "mobile_devices", ["device_uid"])

    op.create_table(
        "device_pairing_codes",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("code_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_device_pairing_codes_expires_at", "device_pairing_codes", ["expires_at"])

    op.add_column("gps_activity_logs", sa.Column("source", sa.String(20), nullable=False, server_default="web"))
    op.add_column(
        "gps_activity_logs",
        sa.Column("device_id", sa.Integer, sa.ForeignKey("mobile_devices.id", ondelete="SET NULL"), nullable=True),
    )
    op.execute("UPDATE gps_activity_logs SET source = 'manual' WHERE is_manual")

    op.create_table(
        "geofence_events",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("device_id", sa.Integer, sa.ForeignKey("mobile_devices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("employee_id", sa.Integer, sa.ForeignKey("employees.id", ondelete="SET NULL"), nullable=True),
        sa.Column("site_id", sa.Integer, sa.ForeignKey("sites.id", ondelete="SET NULL"), nullable=True),
        sa.Column("client_event_id", sa.String(64), nullable=False),
        sa.Column("transition", sa.String(10), nullable=False),
        sa.Column("engine", sa.String(20)),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("latitude", sa.Float),
        sa.Column("longitude", sa.Float),
        sa.Column("accuracy_meters", sa.Float),
        sa.Column("distance_meters", sa.Float),
        sa.Column("is_mock", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("gps_log_id", sa.Integer, sa.ForeignKey("gps_activity_logs.id", ondelete="SET NULL"), nullable=True),
        sa.UniqueConstraint("device_id", "client_event_id", name="uq_geofence_events_device_client"),
    )
    op.create_index("ix_geofence_events_device_id", "geofence_events", ["device_id"])
    op.create_index("ix_geofence_events_employee_id", "geofence_events", ["employee_id"])
    op.create_index("ix_geofence_events_occurred_at", "geofence_events", ["occurred_at"])

    op.create_table(
        "mobile_app_exemptions",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("employee_id", sa.Integer, sa.ForeignKey("employees.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("reason", sa.String(200)),
        sa.Column("created_by_user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "mobile_app_releases",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("version_code", sa.Integer, nullable=False, unique=True),
        sa.Column("version_name", sa.String(30), nullable=False),
        sa.Column("notes", sa.Text),
        sa.Column("file_size", sa.Integer, nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("data", sa.LargeBinary, nullable=False),
        sa.Column("uploaded_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("uploaded_by_user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
    )

    op.execute(
        """
        INSERT INTO permissions (code, description) VALUES
        ('mobile.devices', 'مشاهده‌ی گوشی‌های متصل، ابطال دستگاه، معافیت از اپ اندروید و رویدادهای ورود/خروج خودکار (سایت‌محور)'),
        ('system.mobile_app', 'تنظیمات اپ اندروید و بارگذاری نسخه‌ی APK (کل سیستم)')
        ON CONFLICT (code) DO NOTHING
        """
    )


def downgrade() -> None:
    op.execute(
        "DELETE FROM role_permissions WHERE permission_id IN "
        "(SELECT id FROM permissions WHERE code IN ('mobile.devices','system.mobile_app'))"
    )
    op.execute("DELETE FROM permissions WHERE code IN ('mobile.devices','system.mobile_app')")
    op.drop_table("mobile_app_releases")
    op.drop_table("mobile_app_exemptions")
    op.drop_index("ix_geofence_events_occurred_at", table_name="geofence_events")
    op.drop_index("ix_geofence_events_employee_id", table_name="geofence_events")
    op.drop_index("ix_geofence_events_device_id", table_name="geofence_events")
    op.drop_table("geofence_events")
    op.drop_column("gps_activity_logs", "device_id")
    op.drop_column("gps_activity_logs", "source")
    op.drop_index("ix_device_pairing_codes_expires_at", table_name="device_pairing_codes")
    op.drop_table("device_pairing_codes")
    op.drop_index("ix_mobile_devices_device_uid", table_name="mobile_devices")
    op.drop_index("ix_mobile_devices_employee_id", table_name="mobile_devices")
    op.drop_index("ix_mobile_devices_user_id", table_name="mobile_devices")
    op.drop_table("mobile_devices")
