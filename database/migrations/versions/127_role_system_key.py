"""نقش‌های پیش‌فرض با کلید ثابت (system_key) تا تغییر نام نقش باعث ساخت دوباره‌اش در هر آپدیت نشود

Revision ID: 127
Revises: 126

مشکل: scripts.seed_permissions نقش‌های پیش‌فرض (site_manager، middle_manager، acc_manager، hr-manager) را با «نام»
پیدا می‌کرد؛ اگر ادمین نام را عوض کرده بود، در هر آپدیت یک نقش تازه با نام اولیه ساخته می‌شد.

این Migration:
1. ستون roles.system_key (یکتا، اختیاری) را اضافه می‌کند؛ seed از این به بعد با همین کلید پیدا می‌کند و به نام کاری ندارد.
2. برای هر نقش پیش‌فرض، نقش اصلی را پیدا و کلید را رویش می‌گذارد: بین نقش‌های سیستمی که یا همان نام اولیه را دارند یا
   همان توضیح پیش‌فرض را (نقش تغییرنام‌داده)، قدیمی‌ترین (کمترین id).
3. نسخه‌های تکراری که seed بعد از تغییر نام ساخته (نام اولیه، سیستمی، بدون کلید) فقط اگر به هیچ کاربری داده نشده باشند
   حذف می‌شوند؛ تکراریِ داده‌شده به کسی دست نمی‌خورد (ادمین خودش تصمیم می‌گیرد).
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "127"
down_revision: Union[str, None] = "126"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# همان توضیح‌های پیش‌فرض scripts/seed_permissions.py (برای پیدا کردن نقشِ تغییرنام‌داده)
_DEFAULT_DESCRIPTIONS = {
    "superadmin": "دسترسی کامل — غیرقابل انتصاب از UI",
    "site_manager": "مدیر سایت — حتماً هنگام انتصاب site_id بدهید تا فقط برای همان سایت معتبر باشد",
    "middle_manager": "مدیر میانی — نقش سراسری، می‌تواند هر سایت/واحد/پرسنلی را در کل سازمان هدف بگیرد",
    "acc_manager": (
        "مدیر حسابداری — فقط می‌تواند اطلاعیه فیش حقوقی (Payroll) با آپلود XML بسازد؛ "
        "مخاطبان به‌صورت خودکار از روی کدهای موجود در همان XML تعیین می‌شوند، نه با انتخاب دستی Target"
    ),
    "hr-manager": (
        "مدیر منابع انسانی — اطلاعیه فیش کارکرد (Attendance Card) با آپلود اکسل می‌سازد "
        "(مخاطبان به‌صورت خودکار از روی کدهای موجود در همان اکسل تعیین می‌شوند)، "
        "و گزارش ورود/خروج و «آنلاین در محیط کار» پرسنل را می‌بیند و اصلاح می‌کند."
    ),
}


def upgrade() -> None:
    op.add_column("roles", sa.Column("system_key", sa.String(64), nullable=True))
    op.create_unique_constraint("uq_roles_system_key", "roles", ["system_key"])
    conn = op.get_bind()
    for key, description in _DEFAULT_DESCRIPTIONS.items():
        original = conn.execute(
            sa.text(
                "SELECT id FROM roles WHERE is_system AND system_key IS NULL "
                "AND (name = :key OR description = :desc) ORDER BY id LIMIT 1"
            ),
            {"key": key, "desc": description},
        ).scalar()
        if original is None:
            continue
        conn.execute(sa.text("UPDATE roles SET system_key = :key WHERE id = :id"), {"key": key, "id": original})
        # تکراری‌هایی که seed بعد از تغییر نام ساخته و به هیچ‌کس داده نشده‌اند
        conn.execute(
            sa.text(
                "DELETE FROM roles r WHERE r.is_system AND r.system_key IS NULL AND r.name = :key AND r.id <> :id "
                "AND NOT EXISTS (SELECT 1 FROM user_roles ur WHERE ur.role_id = r.id)"
            ),
            {"key": key, "id": original},
        )


def downgrade() -> None:
    op.drop_constraint("uq_roles_system_key", "roles", type_="unique")
    op.drop_column("roles", "system_key")
