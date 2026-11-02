"""اتوماسیون اداری: ساده‌سازی به تصمیم کاربر (۱۴۰۵/۰۸/۱۱)

- قالب نامه برای همه یکسان است (نه به تفکیک سایت): oa_templates.site_id اختیاری.
- مجوز automation.compose در automation.access ادغام شد: هر کس compose داشت (نقش یا مستقیم، با همان سایت) access می‌گیرد و
  compose حذف می‌شود. ارسال/ارجاع به پرسنل سایت دیگر فقط با automation.access برای همان سایت.
- oa_letters.requires_action و action_due_at: «نیاز به اقدام گیرنده» هنگام ساخت نامه (بدون تیک، گیرنده فقط می‌خواند).

Revision ID: 138
Revises: 137
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "138"
down_revision: Union[str, None] = "137"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column("oa_templates", "site_id", existing_type=sa.Integer(), nullable=True)
    op.add_column("oa_letters", sa.Column("requires_action", sa.Boolean(), nullable=False, server_default=sa.false()))
    op.add_column("oa_letters", sa.Column("action_due_at", sa.DateTime(timezone=True), nullable=True))

    op.execute(
        """
        INSERT INTO role_permissions (role_id, permission_id)
        SELECT rp.role_id, acc.id FROM role_permissions rp
        JOIN permissions c ON c.id = rp.permission_id AND c.code = 'automation.compose'
        CROSS JOIN permissions acc WHERE acc.code = 'automation.access'
        ON CONFLICT (role_id, permission_id) DO NOTHING
        """
    )
    op.execute(
        """
        INSERT INTO user_permissions (user_id, permission_id, site_id, granted_by_user_id)
        SELECT up.user_id, acc.id, up.site_id, up.granted_by_user_id FROM user_permissions up
        JOIN permissions c ON c.id = up.permission_id AND c.code = 'automation.compose'
        CROSS JOIN permissions acc
        WHERE acc.code = 'automation.access' AND NOT EXISTS (
            SELECT 1 FROM user_permissions x
            WHERE x.user_id = up.user_id AND x.permission_id = acc.id AND x.site_id IS NOT DISTINCT FROM up.site_id
        )
        """
    )
    for table in ("role_permissions", "user_permissions"):
        op.execute(f"DELETE FROM {table} WHERE permission_id IN (SELECT id FROM permissions WHERE code = 'automation.compose')")
    op.execute("DELETE FROM permissions WHERE code = 'automation.compose'")
    op.get_bind().execute(
        sa.text("UPDATE permissions SET description = :d WHERE code = 'automation.access'"),
        {"d": "اتوماسیون اداری: کارتابل، نوشتن، ارسال و ارجاع نامه (ارسال به سایت دیگر فقط با همین مجوز برای آن سایت)"},
    )


def downgrade() -> None:
    op.drop_column("oa_letters", "action_due_at")
    op.drop_column("oa_letters", "requires_action")
