"""بکاپ نسخه‌ی ۴: کلیدهای رمزنگاری، تاریخچه‌ی اجرا و تفکیک مجوزهای بکاپ (مهاجرت system.backup)

- backup_keys، backup_runs
- مجوزهای backup.run_view، backup.destinations، backup.download، backup.key_manage، backup.restore
- هر نقش یا مجوز مستقیمی که system.backup دارد، backup.run_view/destinations/download/restore را (با همان سایت) می‌گیرد تا
  هیچ توانایی فعلی از دست نرود؛ backup.key_manage فقط ادمین کل. system.backup تا یک نسخه معادل نگه داشته می‌شود (منسوخ).

Revision ID: 132
Revises: 131
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "132"
down_revision: Union[str, None] = "131"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NEW = {
    "backup.run_view": "پشتیبان‌گیری: اجرای بکاپ و مشاهده‌ی وضعیت و تاریخچه",
    "backup.destinations": "پشتیبان‌گیری: تنظیم زمان‌بندی، مقصدها و سیاست نگهداری",
    "backup.download": "پشتیبان‌گیری: دانلود دستی فایل بکاپ",
    "backup.key_manage": "پشتیبان‌گیری: ساخت/چرخش کلید رمزنگاری و انتخاب حالت کلید",
    "backup.restore": "پشتیبان‌گیری: بازیابی بکاپ روی همین سرور",
}
MIGRATED = ("backup.run_view", "backup.destinations", "backup.download", "backup.restore")


def upgrade() -> None:
    op.create_table(
        "backup_keys",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("key_id", sa.String(32), nullable=False, unique=True),
        sa.Column("mode", sa.String(24), nullable=False),
        sa.Column("public_key", sa.String(128), nullable=False),
        sa.Column("encrypted_private_key", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("retired_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_table(
        "backup_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("set_id", sa.String(32), nullable=False),
        sa.Column("trigger", sa.String(16), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="running"),
        sa.Column("filename", sa.String(128), nullable=True),
        sa.Column("key_id", sa.String(32), nullable=True),
        sa.Column("size", sa.BigInteger(), nullable=True),
        sa.Column("file_count", sa.Integer(), nullable=True),
        sa.Column("files_bytes", sa.BigInteger(), nullable=True),
        sa.Column("manifest_sha256", sa.String(64), nullable=True),
        sa.Column("consistency_method", sa.String(32), nullable=True),
        sa.Column("destinations", sa.JSON(), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("started_by", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_backup_runs_set_id", "backup_runs", ["set_id"])
    op.create_index("ix_backup_runs_started_at", "backup_runs", ["started_at"])

    conn = op.get_bind()
    for code, desc in NEW.items():
        conn.execute(
            sa.text("INSERT INTO permissions (code, description) VALUES (:c, :d) ON CONFLICT (code) DO NOTHING"),
            {"c": code, "d": desc},
        )
    conn.execute(
        sa.text(
            "UPDATE permissions SET description = :d WHERE code = 'system.backup'"
        ),
        {"d": "منسوخ — معادل مجوزهای backup.* (به‌جز key_manage)؛ به‌جای آن مجوزهای جدید پشتیبان‌گیری را بدهید"},
    )
    for code in MIGRATED:
        conn.execute(
            sa.text(
                """
                INSERT INTO role_permissions (role_id, permission_id)
                SELECT rp.role_id, (SELECT id FROM permissions WHERE code = :c)
                FROM role_permissions rp JOIN permissions p ON p.id = rp.permission_id
                WHERE p.code = 'system.backup'
                ON CONFLICT ON CONSTRAINT uq_role_permission DO NOTHING
                """
            ),
            {"c": code},
        )
        conn.execute(
            sa.text(
                """
                INSERT INTO user_permissions (user_id, permission_id, site_id, granted_by_user_id, created_at, updated_at)
                SELECT up.user_id, (SELECT id FROM permissions WHERE code = :c), up.site_id, up.granted_by_user_id,
                       now(), now()
                FROM user_permissions up JOIN permissions p ON p.id = up.permission_id
                WHERE p.code = 'system.backup'
                  AND NOT EXISTS (
                    SELECT 1 FROM user_permissions x
                    WHERE x.user_id = up.user_id AND x.permission_id = (SELECT id FROM permissions WHERE code = :c)
                      AND x.site_id IS NOT DISTINCT FROM up.site_id
                  )
                """
            ),
            {"c": code},
        )


def downgrade() -> None:
    codes = "(" + ",".join(f"'{c}'" for c in NEW) + ")"
    for table in ("role_permissions", "user_permissions"):
        op.execute(f"DELETE FROM {table} WHERE permission_id IN (SELECT id FROM permissions WHERE code IN {codes})")
    op.execute(f"DELETE FROM permissions WHERE code IN {codes}")
    op.drop_table("backup_runs")
    op.drop_table("backup_keys")
